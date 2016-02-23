from AlphaGo.go import GameState
import AlphaGo.go as go
import numpy as np
import unittest

class TestLadders(unittest.TestCase):

    def setUp(self):
        self.s = GameState()
        self.s.do_move((1, 1))  # Black 1
        self.s.do_move((2, 1))  # White 2
        self.s.do_move((2, 0))  # Black 3
        self.s.do_move((6, 0))  # White 4, throw-away
        self.s.do_move((2, 2))  # Black 5
        self.s.do_move((6, 1))  # White 6, throw-away
        # self.s.do_move((3, 0))  # Black 7, ladder capture

    def basic_case(self):
        self.assertTrue(self.s.is_ladder_capture((3, 0)))

# if __name__ == '__main__':
#     unittest.main()
