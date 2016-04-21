import argparse
from AlphaGo.ai import ProbabilisticPolicyPlayer
from AlphaGo.go import GameState
from AlphaGo.models.policy import CNNPolicy
from AlphaGo.preprocessing.preprocessing import Preprocess
import h5py
import numpy as np
import os
#
# from ipdb import set_trace as BP


def save(out_pth, X, winners_list, colors_list):
    tmp_file = os.path.join(os.path.dirname(out_pth), ".tmp." + os.path.basename(out_pth))
    f = h5py.File(tmp_file, 'w')
    try:
        states = f.create_dataset(
            'states',
            dtype=np.uint8,
            chunks=(min(64, X.shape[0]),) + X.shape[1:],      # approximately 1MB chunks
            compression="lzf",
            data=X)
        winners = f.create_dataset('winners', data=winners_list)
        colors = f.create_dataset('colors', data=colors_list)
        f.close()
        os.rename(tmp_file, out_pth)
    except Exception as e:
        os.remove(tmp_file)
        raise e
    return


def play_batch(player_RL, player_SL, batch_size, features):
    """Play a batch of games in parallel and return one training pair
    from each game.
    """

    def do_move(states, moves):
        for st, mv in zip(states, moves):
            if not st.is_end_of_game:
                # Only do more moves if not end of game already
                st.do_move(mv)
        return states

    def do_rand_move(states, player, player_RL):
        """Do a uniform-random move over legal moves and record info for
        training. Only gets called once per game.
        """
        colors = [st.current_player for st in states]  # Record player color
        legal_moves = [st.get_legal_moves() for st in states]
        rand_moves = [lm[np.random.choice(len(lm))] for lm in legal_moves]
        states = do_move(states, rand_moves)
        player = player_RL
        X_list = [st.copy() for st in states]  # For later 1hot preprocessing
        return X_list, colors, states, player

    def convert(X_list, preprocessor):
        """Convert states to 1-hot and concatenate. X's are game state objects.
        """
        states = np.concatenate(
            [preprocessor.state_to_tensor(X) for X in X_list], axis=0)
        return states

    # Lists of game training pairs (1-hot)
    preprocessor = Preprocess(features)
    player = player_SL
    states = [GameState() for i in xrange(batch_size)]
    # Randomly choose turn to play uniform random. Move prior will be from SL
    # policy. Moves after will be from RL policy.
    i_rand_move = np.random.choice(range(450))
    turn = 0
    while True:
        # Do moves (black)
        if turn == i_rand_move:
            # Make random move, then switch from SL to RL policy
            X_list, colors, states, player = do_rand_move(states, player,
                                                          player_RL)
        else:
            # Get moves (batch)
            moves_black = player.get_moves(states)
            # Do moves (black)
            states = do_move(states, moves_black)
        turn += 1
        # Do moves (white)
        if turn == i_rand_move:
            # Make random move, then switch from SL to RL policy
            X_list, colors, states, player = do_rand_move(states, player,
                                                          player_RL)
        else:
            moves_white = player.get_moves(states)
            states = do_move(states, moves_white)
        turn += 1
        # If all games have ended, we're done. Get winners.
        done = [st.is_end_of_game or st.turns_played > 500 for st in states]
        print turn
        if all(done):
            break
    # Concatenate training examples
    X = convert(X_list, preprocessor)
    winners = [st.get_winner() for st in states]
    print 'i_rand_move: ', i_rand_move
    print 'colors: ', colors
    return X, winners, colors


def run(player_RL, player_SL, out_pth, n_training_pairs, batch_size, features):
    X_list = []
    winners_list = []
    colors_list = []
    for n in xrange(n_training_pairs / batch_size):
        X, winners, colors = play_batch(player_RL, player_SL, batch_size, features)
        X_list.append(X)
        winners_list.extend(winners)
        colors_list.extend(colors)
    # Concatenate over batches to make one HDF5 file
    X = np.concatenate(X_list, axis=0)
    save(out_pth, X, winners_list, colors_list)
    return


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Play games used for training'
                                     'value network (third phase of pipeline). '
                                     'The final policy from the RL phase plays '
                                     'against itself and training pairs for value '
                                     'network are generated from the outcome in each '
                                     'games, following an off-policy, uniform random move')
    parser.add_argument("SL_weights_path", help="Path to file with supervised "
                        "learning policy weights.")
    parser.add_argument("RL_weights_path", help="Path to file with reinforcement "
                        "learning policy weights.")
    parser.add_argument("model_path", help="Path to network architecture file.")
    parser.add_argument("--out_pth", "-o", help="Path to where the training "
                        "pairs will be saved. Default: None", default=None)
    parser.add_argument("--load_from_file", help="Path to HDF5 file to continue from."
                        " Default: None", default=None)
    parser.add_argument(
        "--n_training_pairs", help="Number of training pairs to generate. "
        "(Default: 20)", type=int, default=2)
    parser.add_argument(
        "--batch_size", help="Number of games to run in parallel. "
        "(Default: 10)", type=int, default=2)
    args = parser.parse_args()

    # Load architecture and weights from file
    policy_SL = CNNPolicy.load_model(args.model_path)
    features = policy_SL.preprocessor.feature_list
    policy_SL.model.load_weights(args.SL_weights_path)
    policy_RL = CNNPolicy.load_model(args.model_path)
    policy_RL.model.load_weights(args.RL_weights_path)
    # Create player object that plays against itself (for both RL and SL phases)
    player_RL = ProbabilisticPolicyPlayer(policy_RL)
    player_SL = ProbabilisticPolicyPlayer(policy_SL)
    run(player_RL, player_SL, args.out_pth, args.n_training_pairs,
        args.batch_size, features)
