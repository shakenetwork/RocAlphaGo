import numpy as np

WHITE = -1
BLACK = +1
EMPTY = 0
PASS_MOVE = None


class GameState(object):
	"""State of a game of Go and some basic functions to interact with it
	"""

	def __init__(self, size=19):
		self.board = np.zeros((size, size))
		self.board.fill(EMPTY)
		self.size = size
		self.turns_played = 0
		self.current_player = BLACK
		self.ko = None
		self.history = []
		self.num_black_prisoners = 0
		self.num_white_prisoners = 0
		# Sequences of moves that consitute ladder capture, cached for more
		# efficient computation
		self.cached_ladders = []
		# `self.liberty_sets` is a 2D array with the same indexes as `board`
		# each entry points to a set of tuples - the liberties of a stone's
		# connected block. By caching liberties in this way, we can directly
		# optimize update functions (e.g. do_move) and in doing so indirectly
		# speed up any function that queries liberties
		self.liberty_sets = [[set() for _ in range(size)] for _ in range(size)]
		for x in range(size):
			for y in range(size):
				self.liberty_sets[x][y] = set(self._neighbors((x,y)))
		# separately cache the 2D numpy array of the _size_ of liberty sets
		# at each board position
		self.liberty_counts = np.zeros((size,size))
		self.liberty_counts.fill(-1)
		# initialize liberty_sets of empty board: the set of neighbors of each position
		# similarly to `liberty_sets`, `group_sets[x][y]` points to a set of tuples
		# containing all (x',y') pairs in the group connected to (x,y)
		self.group_sets = [[set() for _ in range(size)] for _ in range(size)]

	def get_group(self, position):
		"""Get the group of connected same-color stones to the given position

		Keyword arguments:
		position -- a tuple of (x, y)
		x being the column index of the starting position of the search
		y being the row index of the starting position of the search

		Return:
		a set of tuples consist of (x, y)s which are the same-color cluster 
		which contains the input single position. len(group) is size of the cluster, can be large. 
		"""
		(x, y) = position
		# given that this is already cached, it is a fast lookup
		return self.group_sets[x][y]

	def get_groups_around(self, position):
		"""returns a list of the unique groups adjacent to position

		'unique' means that, for example in this position:

			. . . . .
			. B W . .
			. W W . .
			. . . . .
			. . . . .

		only the one white group would be returned on get_groups_around((1,1))
		"""
		groups = []
		for (nx,ny) in self._neighbors(position):
			if self.board[nx][ny] != EMPTY:
				group = self.group_sets[nx][ny]
				group_member = next(iter(group)) # pick any stone
				if not any(group_member in g for g in groups):
					groups.append(group)
		return groups

	def _on_board(self, position):
		"""simply return True iff position is within the bounds of [0, self.size)
		"""
		(x,y) = position
		return x >= 0 and y >= 0 and x < self.size and y < self.size

	def _neighbors(self, position):
		"""A private helper function that simply returns a list of positions neighboring
		the given (x,y) position. Basically it handles edges and corners.
		"""
		(x,y) = position
		return filter(self._on_board, [(x-1, y), (x+1, y), (x, y-1), (x, y+1)])
	
	def _update_neighbors(self, position):
		"""A private helper function to update self.group_sets and self.liberty_sets 
		given that a stone was just played at `position`
		"""
		(x,y) = position

		merged_group = set()
		merged_group.add(position)
		merged_libs  = self.liberty_sets[x][y]
		for (nx, ny) in self._neighbors(position):
			# remove (x,y) from liberties of neighboring positions
			self.liberty_sets[nx][ny] -= set([position])
			# if neighbor was opponent, update group's liberties count
			# (current_player's groups will be updated below regardless)
			if self.board[nx][ny] == -self.current_player:
				new_liberty_count = len(self.liberty_sets[nx][ny])
				for (gx,gy) in self.group_sets[nx][ny]:
					self.liberty_counts[gx][gy] = new_liberty_count
			# MERGE group/liberty sets if neighbor is the same color
			# note: this automatically takes care of merging two separate
			# groups that just became connected through (x,y)
			elif self.board[x][y] == self.board[nx][ny]:
				merged_group |= self.group_sets[nx][ny]
				merged_libs  |= self.liberty_sets[nx][ny]

		# now that we have one big 'merged' set for groups and liberties, loop 
		# over every member of the same-color group to update them
		# Note: neighboring opponent groups are already updated in the previous loop
		count_merged_libs = len(merged_libs)
		for (gx,gy) in merged_group:
			self.group_sets[gx][gy] = merged_group
			self.liberty_sets[gx][gy] = merged_libs
			self.liberty_counts[gx][gy] = count_merged_libs

	def _remove_group(self, group):
		"""A private helper function to take a group off the board (due to capture),
		updating group sets and liberties along the way
		"""
		for (x,y) in group:
			self.board[x,y] = EMPTY
		for (x,y) in group:
			# clear group_sets for all positions in 'group'
			self.group_sets[x][y] = set()
			self.liberty_sets[x][y] = set()
			self.liberty_counts[x][y] = 0
			for (nx,ny) in self._neighbors((x,y)):
				if self.board[nx,ny] == EMPTY:
					# add empty neighbors of (x,y) to its liberties
					self.liberty_sets[x][y].add((nx,ny))
					self.liberty_counts[x][y] += 1
				else:
					# add (x,y) to the liberties of its nonempty neighbors
					self.liberty_sets[nx][ny].add((x,y))
					self.liberty_counts[nx][ny] += 1

	def copy(self):
		"""get a copy of this Game state
		"""
		other = GameState(self.size)
		other.board = self.board.copy()
		other.turns_played = self.turns_played
		other.current_player = self.current_player
		other.ko = self.ko
		other.history = self.history
		other.num_black_prisoners = self.num_black_prisoners
		other.num_white_prisoners = self.num_white_prisoners

		# update liberty and group sets. Note: calling set(a) on another set
		# copies the entries (any iterable as an argument would work so
		# set(list(a)) is unnecessary)
		for x in range(self.size):
			for y in range(self.size):
				other.group_sets[x][y] = set(self.group_sets[x][y])
				other.liberty_sets[x][y] = set(self.liberty_sets[x][y])
		other.liberty_counts = self.liberty_counts.copy()
		return other

	def is_suicide(self, action):
		"""return true if having current_player play at <action> would be suicide
		"""
		(x,y) = action
		num_liberties_here = len(self.liberty_sets[x][y])
		if num_liberties_here == 0:
			# no liberties here 'immediately'
			# but this may still connect to another group of the same color
			for (nx,ny) in self._neighbors(action):
				# check if we're saved by attaching to a friendly group that has
				# liberties elsewhere
				is_friendly_group = self.board[nx,ny] == self.current_player
				group_has_other_liberties = len(self.liberty_sets[nx][ny] - set([action])) > 0
				if is_friendly_group and group_has_other_liberties:
					return False
				# check if we're killing an unfriendly group
				is_enemy_group = self.board[nx,ny] == -self.current_player
				if is_enemy_group and (not group_has_other_liberties):
					return False
			# checked all the neighbors, and it doesn't look good.
			return True
		return False

	def is_legal(self, action):
		"""determine if the given action (x,y tuple) is a legal move

		note: we only check ko, not superko at this point (TODO?)
		"""
		# passing move
		if action is PASS_MOVE:
			return True
		(x,y) = action
		empty = self.board[x][y] == EMPTY
		suicide = self.is_suicide(action)
		ko = action == self.ko
		return self._on_board(action) and (not suicide) and (not ko) and empty 

	def is_eye(self, position, owner):
		"""returns whether the position is empty and is surrounded by all stones of 'owner'
		"""
		(x,y) = position
		if self.board[x,y] != EMPTY:
			return False

		for (nx,ny) in self._neighbors(position):
			if self.board[nx,ny] != owner:
					return False
		return True

	def is_ladder_capture(self, action):
		"""
		Test whether action would result in a ladder capture by current player.
		This function does a full roll-out of the ladder sequence to test whether
		it ends in successful capture.
		"""
		# np.set_printoptions(linewidth=150)

		def _get_9neighbors(pos):
			"""Private function of is_ladder_capture. Returns the 9 directly neighboring
			positions around pos."""
			neighbors = [[pos[0] - 1, pos[1] - 1],
						 [pos[0], pos[1] - 1],
				         [pos[0] + 1, pos[1] - 1],
				         [pos[0] + 1, pos[1]],
				         [pos[0] + 1, pos[1] + 1],
				         [pos[0], pos[1] + 1],
				         [pos[0] - 1, pos[1] + 1],
				         [pos[0] - 1, pos[1]]]
			return neighbors

		def play_out_ladder(prey_move, lboard, hunter_move):
			"""Keep playing moves until ladder capture or escape is reached.
			Args:
			prey_move (Tuple) -- Prey's first move after `action`. Must be in a 1-lib
					             space
			lboard (array) -- Copy of board, to be used for testing this ladder move.
			hunter_move (tuple) -- Hunter's previous move (i.e. `action`).
			"""
			# Play prey's 1-lib
			lboard.do_move(prey_move)
			# Check that exactly 2 liberties were generated at prey_move
			prey_libs = lboard.liberty_sets[prey_move[0]][prey_move[1]]
			if len(prey_libs) == 2:
				while True:
					# Hunter move should be diagonal from previous move, so choose the one
					# that meets this criterion. (TODO: May be cases where this isn't correct)
					h_move = []
					for lib in prey_libs:
						# Check that move is diagonal from `hunter_move`
						if lib[0] != hunter_move[0] and lib[1] != hunter_move[1]:
							h_move.append(lib)
					if len(h_move) == 1:
						# Got the expected number of hunter moves diagonal to `hunter_move`, so
						# continue. Now play hunter move there.
						hunter_move = h_move[0]
						lboard.do_move(hunter_move)
						# Now check that this move generates a 1lib for prey and isn't a
						# capture by hunter
						prey_move = lboard.history[-2]
						if lboard.board[prey_move] == 0:
							# Is capture by hunter (before reaching edge of board), so successful
							# ladder capture
							# print "Was successful ladder capture (before edge of board reached)."
							return True
						elif lboard.liberty_counts[prey_move] == 1 and \
							lboard.board[prey_move] != 0:
							# Do prey move in the 1lib position
							one_lib_move = tuple(lboard.liberty_sets[
								prey_move[0]][prey_move[1]])[0]
							print one_lib_move
							lboard.do_move(one_lib_move)
							# Update prey_move
							prey_move = lboard.history[-1]
							# Update prey_libs, which gives set of libs at prey move
							prey_libs = lboard.liberty_sets[prey_move[0]][prey_move[1]]
							# move_sequence.extend(lboard.history[-2:])  # TODO
						else:
							# Prey's second move escapes ladder
							# print "Prey escaped. Not ladder."
							was_ladder_capture = False
							break
					else:
						# There were either no diagonal moves available to hunter for next
						# move, or there were more than one. (TODO: Is the latter possible?)
						# First, check if this is because we've reached end of ladder, and
						# hunter can finally capture all prey stones. If this is the case,
						# prey should only have one liberty at their last move.
						if len(prey_libs) == 1:
							# Now see if hunter moving into that liberty would cause a
							# capture.
							lboard_tmp = lboard.copy()
							lboard_tmp.do_move(list(prey_libs)[0])
							if lboard_tmp.board[prey_move] == 0:
								# Was a capture
								# print "Was successful ladder capture."
								return True
						# Wasn't because we reached end of ladder. Must be because of an
						# escape stone in the ladder path.
						# print "No diagonal moves for hunter. Not a ladder."
						was_ladder_capture = False
						break
			else:
				# Initial prey move did not generate exactly 2 liberties
				# print "Prey move did not generate exactly 2 liberties. Not a ladder."
				was_ladder_capture = False
			return was_ladder_capture

		# TODO: Use cached away ladders for more efficient computation
		tmp = self.copy()
		tmp.do_move(action)
		if np.any(tmp.liberty_counts == 1):
			# Found 1libs on board
			# print 'Found 1-libs on board...'
			is_one_lib = np.zeros_like(tmp.liberty_counts)
			is_one_lib[tmp.liberty_counts == 1] = 1  # 1 where 1lib, zero otherwise
			# select only those within the neighborhood of 'action'
			neighors = _get_9neighbors(action)
			one_lib_neighbors = []  # List of 1lib positions in neighborhood of action
			for n in neighors:
				if is_one_lib[n[0], n[1]]:
					one_lib_neighbors.append(n)
			# select only those 1-libs that belong to prey
			one_lib_prey = []
			for l in one_lib_neighbors:
				if tmp.board[l[0], l[1]] == tmp.current_player:
					one_lib_prey.append(list(l))
			if len(one_lib_prey) > 0:
				# Prey has 1lib after black's move. Continue to play out ladder.
				# print 'Found 1-libs belonging to opponent...'
				# Try each of prey's 1libs in turn to see if it's a ladder.
				# TODO: Even possible to have multiple ladder options
				# for the same move?
				for lib in one_lib_prey:
					tmp1 = tmp.copy()
					# Get open space
					prey_move = list(tmp1.liberty_sets[lib[0]][lib[1]])[0]
					# Play out rest of ladder until ladder escape or capture reached
					is_ladder = play_out_ladder(prey_move, tmp, action)
					if is_ladder:
						return True
					# If successful ladder capture, cache away for later (TODO)
					# self.cached_ladders.append(tmp1)
				# We've checked all opponent 1-libs, and none resulted in
				# exactly 2 libs, so 'action' is not a ladder capture.
				# print "None of the opponent 1-lib plays resulted in 2 liberties. Not a ladder."
				return False
			else:
				# print "Opponent had no 1-libs. Not a ladder."
				return False  # Not a ladder, because opponent has no 1-lib groups
		else:
			# print "Found no 1-libs. Not a ladder."
			# Not a ladder, because no 1-lib groups on board
			return False

	def get_legal_moves(self):
		moves = []
		for x in range(self.size):
			for y in range(self.size):
				if self.is_legal((x,y)):
					moves.append((x,y))
		return moves

	def do_move(self, action):
		"""Play current_player's color at (x,y)

		If it is a legal move, current_player switches to the other player
		If not, an IllegalMove exception is raised
		"""
		if self.is_legal(action):
			# reset ko
			self.ko = None
			if action is not PASS_MOVE:
				(x,y) = action
				self.board[x][y] = self.current_player
				self._update_neighbors(action)
				
				# check neighboring groups' liberties for captures
				for (nx, ny) in self._neighbors(action):
					if self.board[nx,ny] == -self.current_player and len(self.liberty_sets[nx][ny]) == 0:
						# capture occurred!
						captured_group = self.group_sets[nx][ny]
						num_captured = len(captured_group)
						self._remove_group(captured_group)
						if self.current_player == BLACK:
							self.num_white_prisoners += num_captured
						else:
							self.num_black_prisoners += num_captured
						# check for ko
						if num_captured == 1:
							# it is a ko iff, were the opponent to play at the captured position,
							# it would recapture (x,y) only
							# (a bigger group containing xy may be captured - this is 'snapback')
							would_recapture = len(self.liberty_sets[x][y]) == 1
							recapture_size_is_1 = len(self.group_sets[x][y]) == 1
							if would_recapture and recapture_size_is_1:
								# note: (nx,ny) is the stone that was captured
								self.ko = (nx,ny)
			# next turn
			self.current_player = -self.current_player
			self.turns_played += 1
			self.history.append(action)
		else:
			raise IllegalMove(str(action))

	def from_sgf(self, sgf_string):
		raise NotImplementedError()

	def to_sgf(self, sgf_string):
		raise NotImplementedError()


class IllegalMove(Exception):
	pass
