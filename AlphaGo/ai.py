class GreedyPolicyPlayer(object):
    """A CNN player that uses a greedy policy (i.e. chooses the highest probability
       move at each point)
    """
    def __init__(self, policy_function):
        self.policy = policy_function

    def get_move(self, state):
        action_probs = self.policy.eval_state(state)
        if len(action_probs) > 0:
            max_prob = max(action_probs, key=lambda (a, p): p)
            return max_prob[0]
        else:
            # No legal moves available, do so pass move
            return None
