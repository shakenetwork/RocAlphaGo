class GreedyPolicyPlayer(object):
    def __init__(self, policy_function):
        self.policy = policy_function

    def get_move(self, state):
        action_probs = self.policy.eval_state(state)
        max_prob = max(action_probs, key=lambda (a, p): p)
        return max_prob[0]


from models.policy import CNNPolicy
from interface.Play import play_match
from ipdb import set_trace as BP
features = ["board", "ones", "turns_since", "liberties", "capture_size",
    "self_atari", "liberties_after", "ladder_capture", "ladder_escape",
    "sensibleness", "zeros"]
policy1 = CNNPolicy(features)
policy2 = CNNPolicy(features)
player1 = GreedyPolicyPlayer(policy1)
player2 = GreedyPolicyPlayer(policy2)

match = play_match(player1, player2, 'test')
while True:
    end_of_game = match.play()
    BP()
    if end_of_game:
        break
