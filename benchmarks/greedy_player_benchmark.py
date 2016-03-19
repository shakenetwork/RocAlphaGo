from AlphaGo.ai import GreedyPolicyPlayer
from AlphaGo.models.policy import CNNPolicy
from interface.Play import play_match
import time
import numpy as np
np.set_printoptions(linewidth=80)


features = ["board", "ones", "turns_since", "liberties", "capture_size",
            "self_atari_size", "liberties_after",
            "sensibleness", "zeros"]
policy1 = CNNPolicy(features)
policy2 = CNNPolicy(features)
player1 = GreedyPolicyPlayer(policy1)
player2 = GreedyPolicyPlayer(policy2)

match = play_match(player1, player2, 'test')

t0 = time.time()
while True:
    end_of_game = match.play()
    print "turns played:", match.state.turns_played
    if end_of_game:
        break
    if match.state.turns_played % 1 == 0:
        print match.state.board
    # Game may go on forever (TODO: End of game criteria)
    elif match.state.turns_played > 1000:
        break
t1 = time.time()
runtime = t1 - t0
print "Runtime: ", runtime
print "Total moves: ", match.state.turns_played
# print "Final board: \n", match.state.board
