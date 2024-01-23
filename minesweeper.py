from tkinter import *
from tkinter import messagebox as tkMessageBox
from datetime import time, date, datetime
from itertools import combinations
import argparse
import random
import platform
import numpy as np

level_dict = {'Easy': (9, 9, 10), 'Medium': (16, 16, 25), 'Hard': (30, 16, 99)}
parser = argparse.ArgumentParser()
parser.add_argument('--level', type=str, choices=['Easy', 'Medium', 'Hard'], default='Easy')
parser.add_argument('--AI', type=eval, choices=[True, False], default=True)
args = parser.parse_args()

SIZE_X, SIZE_Y = level_dict[args.level][0], level_dict[args.level][1]
NUM_MINES = level_dict[args.level][2]

STATE_DEFAULT = 0
STATE_CLICKED = 1
STATE_FLAGGED = 2

BTN_CLICK = "<Button-1>"
BTN_FLAG = "<Button-2>" if platform.system() == 'Darwin' else "<Button-3>"

window = None
def printClause(clause):
    for literal in clause.literals:
        print(literal.id, literal.bar, end=",")
    print("\n")
    return

class Literal:
    def __init__(self, ID, bar):
        self.id = ID # id of the cell in the game board
        self.bar = bar  # indicate that if the cell is safe 

    def __hash__(self):
        return hash((self.id, self.bar))
    
    def __eq__(self, other):
        return self.id == other.id and self.bar == other.bar

class Clause:
    def __init__(self, literals):
        self.literals = literals # a tuple containing several literals
        self.len = len(literals) # len of the clause

    def __hash__(self):
        return hash((self.literals, self.len))
    
    def __eq__(self, other):
        return self.literals == other.literals
    
class Player:
    def __init__(self):
        self.KB = None  # a set of CNF caluses for resolution
        self.KB0 = None # a set of literals representing marked cells
        
    def get_single_literal_clause(self): # return one of the single-literal clause
        for clause in self.KB:           # to the game module if it exists
            if clause.len == 1:
                return clause
        return None
    
    def match_remaining_in_KB(self, literal):   #  Process the "matching" of the returned single-literal clause to 
        tmp = []                                #　all the remaining clauses in the KB after it was removed from KB to KB0.
        for clause in self.KB:
            if literal in clause.literals:
                tmp.append(clause)
        for clause in tmp:
            self.KB.remove(clause)

        tmp = []
        for clause in self.KB:
            ids = [lit.id for lit in clause.literals]
            if literal.id in ids:
                tmp.append(clause)
        for clause in tmp:
            self.KB.remove(clause)
            literals_set = set(clause.literals)
            literals_set.remove(Literal(literal.id, not literal.bar))
            self.KB.add(Clause(tuple(literals_set)))
                
    def pair_wise_matching(self): # Apply when there is no single-literal clause in the KB
        clause_list = list(self.KB) 
        for i in range(len(clause_list)):
            for j in range(i+1, len(clause_list)):
                if clause_list[i].len == 2 or clause_list[j].len == 2: # to keep the KB from growing too fast, only
                    literals_tuple1 = clause_list[i].literals          # match clause pairs where one clause has only two literals.
                    literals_tuple2 = clause_list[j].literals
                    cnt = 0
                    for literal1 in literals_tuple1:
                        for literal2 in literals_tuple2:
                            if literal1.id == literal2.id and literal1.bar != literal2.bar:
                                lhs, rhs = literal1, literal2
                                cnt += 1
                    if cnt == 1:
                        lhs_set = set(literals_tuple1)
                        rhs_set = set(literals_tuple2)
                        lhs_set.remove(lhs)
                        rhs_set.remove(rhs)
                        self.insertKB(tuple(lhs_set.union(rhs_set)))
        return

    def insertKB(self, clause_tuple): 
        literals = self.resolution_byKB0(clause_tuple) # Do resolution of the new clause with all the clauses in KB0
        if literals:
            clause = Clause(tuple(literals))
            for element in self.KB: # Check for subsumption with all the clauses in KB
                if self.check_subsumption(element, clause): 
                    return
            tmp = []
            for element in self.KB:
                if self.check_subsumption(clause, element):
                    tmp.append(element)

            for element in tmp:
                self.KB.remove(element)
            self.KB.add(clause)
        return

    def resolution_byKB0(self, literals_tuple):
        literals_set = set(literals_tuple)
        if literals_set & self.KB0: # If the clause contains literals which have been already 
            return None             # in KB0, we will not insert them into KB.
        
        ids = [lit.id for lit in self.KB0]
        tmp = []
        for literal in literals_set: # If the clause contains literals whose complementary literals
            if literal.id in ids:    # are in KB0, we remove these literals from the caluse.
                tmp.append(literal)

        for element in tmp:
            literals_set.remove(element)

        return literals_set #return set
    
    def check_subsumption(self, clause1, clause2): # check if the left clause is the subset of the 
        for literal in clause1.literals:           # the right clause
            if literal not in clause2.literals:
                return False
        return True

class Minesweeper:
    def __init__(self, tk):
        self.player = Player() # Player Module
        # import images
        self.images = {
            "plain": [PhotoImage(file = "images/tile_grey"+str(i)+".png")  for i in range(9)],
            "numbers": [PhotoImage(file = "images/tile_green"+str(i)+".png")  for i in range(9)],
            "mine": PhotoImage(file = "images/tile_mine.gif"),
            "flag": PhotoImage(file = "images/tile_flag.gif"),
            "wrong": PhotoImage(file = "images/tile_wrong.gif")
        }

        # set up frame
        self.tk = tk
        self.frame = Frame(self.tk, bg='black', bd=5)
        self.frame.pack()

        # set up labels/UI
        self.labels = {
            "time": Label(self.frame, text = "00:00:00", font=("Arial", 20)),
            "mines": Label(self.frame, text = "Mines: 0", font=("Arial", 15)),
            "flags": Label(self.frame, text = "Flags: 0", font=("Arial", 15))
        }
        self.labels["time"].grid(row = 0, column = 0, columnspan = SIZE_Y) # top full width
        self.labels["mines"].grid(row = SIZE_X+1, column = 0, columnspan = int(SIZE_Y/2)) # bottom left
        self.labels["flags"].grid(row = SIZE_X+1, column = int(SIZE_Y/2)-1, columnspan = int(SIZE_Y/2)) # bottom right
        self.labels["time"].config(width=20, height=1)
        
        self.restart() # start game
        self.updateTimer() # init timer
    
        if args.AI:
            self.inference()
            
    def id_to_crd(self, id):
        return id // SIZE_Y, id % SIZE_Y
    
    def inference(self):
        choose = self.player.get_single_literal_clause() # get a single-literal clause from the KB
        if choose:
            literal = choose.literals[0]
            x, y = self.id_to_crd(literal.id) # convert the id of a cell to its coordinate
            self.player.KB.remove(choose)
            self.player.KB0.add(literal)
            self.player.match_remaining_in_KB(literal) 
            if literal.bar:
                self.onClick(self.tiles[x][y]) # mark the cell as safe
            else:
                self.onRightClick(self.tiles[x][y]) # flagging the cell with a mine
            
            if literal.bar: # Get hints if the marked cell is safe.
                tile = self.tiles[x][y]
                neighbors = self.getNeighbors(x, y)
                if tile["mines"] == 0: 
                    for tile in neighbors:
                        self.player.insertKB((Literal(tile["id"], True),))
                elif tile["near_tiles"] == tile["mines"]:
                    for tile in neighbors:
                        self.player.insertKB((Literal(tile["id"], False),))
                else: 
                    literals = [Literal(tile["id"], False) for tile in neighbors]
                    combo = combinations(literals, tile["near_tiles"] - tile["mines"] + 1)
                    for ele in combo:
                        self.player.insertKB(ele)

                    literals = [Literal(tile["id"], True) for tile in neighbors]
                    combo = combinations(literals, tile["mines"] + 1)
                    for ele in combo:
                        self.player.insertKB(ele)
        else:
            if SIZE_X * SIZE_Y - self.correctFlagCount -self.flagCount < 30: # Consider the global constraint as a hint 
                # global hint                                                # if the number of unmarked cells is smaller 
                m, n = 0, 0                                                  # threshold(30).
                ids = []
                for x in range(SIZE_X):
                    for y in range(SIZE_Y):
                        if self.tiles[x][y]["state"] ==  STATE_DEFAULT:
                            m += 1
                            ids.append(self.tiles[x][y]["id"])
                            if self.tiles[x][y]["isMine"]:
                                n += 1

                literals = [Literal(id, False) for id in ids]
                combo = combinations(literals, m - n + 1)
                for ele in combo:
                    self.player.insertKB(ele)
                
                literals = [Literal(id, True) for id in ids]
                combo = combinations(literals, n + 1)
                for ele in combo:
                    self.player.insertKB(ele)

            self.player.pair_wise_matching() # Do pairwise "matching" of the clauses in the KB
                                             # to generate new clauses for further resolution
            # print("pair wise matching: ")
            # for clause in self.player.KB:
            #     printClause(clause)
            
        print("KB len:", len(self.player.KB), end=', ')
        print("KB0 len:", len(self.player.KB0))
        self.frame.after(20, self.inference) #定時走一步

    def setup(self): # Set up the new game
        # create flag and clicked tile variables
        self.flagCount = 0
        self.correctFlagCount = 0
        self.clickedCount = 0
        self.startTime = None
        # create buttons
        self.tiles = {i : {} for i in range(0, SIZE_X)}
        self.mines = NUM_MINES
        for x in range(0, SIZE_X):
            for y in range(0, SIZE_Y):
                id = x * SIZE_Y + y
                tile = {
                    "id": id,
                    "isMine": False,
                    "state": STATE_DEFAULT,
                    "coords": {
                        "x": x,
                        "y": y
                    },
                    "button": None,
                    "near_tiles": 0,
                    "mines": 0
                }
                self.tiles[x][y] = tile

        points = [(i, j) for i in range(SIZE_X) for j in range(SIZE_Y)]
        mine_points = random.sample(points, self.mines) # sample unsafe cells from the set of all cells
        for point in mine_points:
            self.tiles[point[0]][point[1]]["isMine"] = True

        difference = list(set(points) - set(mine_points))
        initial_safe_points = random.sample(difference, round(np.sqrt(SIZE_X * SIZE_Y))) # sample safe cells from the set of all cells

        self.player.KB = set([Clause((Literal(x * SIZE_Y + y, True),)) for x, y in initial_safe_points]) # initialize the KB
        self.player.KB0 = set()
        # loop again to find nearby mines and display number on tile
        for x in range(0, SIZE_X): # initialize the game board
            for y in range(0, SIZE_Y):
                mc = 0
                for n in self.getNeighbors(x, y):
                    mc += 1 if n["isMine"] else 0
                self.tiles[x][y]["mines"] = mc
                self.tiles[x][y]["near_tiles"] = len(self.getNeighbors(x, y))
                if self.tiles[x][y]["isMine"]:
                    self.tiles[x][y]["button"] = Button(self.frame, image = self.images["mine"])
                else:
                    self.tiles[x][y]["button"] = Button(self.frame, image = self.images["plain"][mc])
                self.tiles[x][y]["button"].bind(BTN_CLICK, self.onClickWrapper(x, y)) #要用 labmda
                self.tiles[x][y]["button"].bind(BTN_FLAG, self.onRightClickWrapper(x, y)) #要用 labmda
                self.tiles[x][y]["button"].grid(row = x+1, column = y) # offset by 1 row for timer
                self.tiles[x][y]["button"].config(width=50, height=25) ###

    def restart(self): # restart the game
        self.setup()
        self.refreshLabels()

    def refreshLabels(self):
        self.labels["flags"].config(text = "Flags: "+str(self.flagCount))
        self.labels["mines"].config(text = "Mines: "+str(self.mines))

    def gameOver(self, won): # terminate the game
        for x in range(0, SIZE_X):
            for y in range(0, SIZE_Y):
                if self.tiles[x][y]["isMine"] == False and self.tiles[x][y]["state"] == STATE_FLAGGED:
                    self.tiles[x][y]["button"].config(image = self.images["wrong"])
                if self.tiles[x][y]["isMine"] == True and self.tiles[x][y]["state"] != STATE_FLAGGED:
                    self.tiles[x][y]["button"].config(image = self.images["mine"])

        self.tk.update()

        msg = "You Win! Play again?" if won else "You Lose! Play again?"
        res = tkMessageBox.askyesno("Game Over", msg)
        if res:
            self.restart()
        else:
            self.tk.quit()

    def updateTimer(self):
        ts = "00:00:00"
        if self.startTime != None:
            delta = datetime.now() - self.startTime
            ts = str(delta).split('.')[0] # drop ms
            if delta.total_seconds() < 36000:
                ts = "0" + ts # zero-pad
        self.labels["time"].config(text = ts)
        self.frame.after(100, self.updateTimer) #定時刷新介面(100ms)

    def getNeighbors(self, x, y):
        neighbors = []
        coords = [
            {"x": x-1,  "y": y-1},  #top right
            {"x": x-1,  "y": y},    #top middle
            {"x": x-1,  "y": y+1},  #top left
            {"x": x,    "y": y-1},  #left
            {"x": x,    "y": y+1},  #right
            {"x": x+1,  "y": y-1},  #bottom right
            {"x": x+1,  "y": y},    #bottom middle
            {"x": x+1,  "y": y+1},  #bottom left
        ]
        for n in coords:
            try:
                neighbors.append(self.tiles[n["x"]][n["y"]])
            except KeyError:
                pass
        return neighbors

    def onClickWrapper(self, x, y):
        return lambda Button: self.onClick(self.tiles[x][y], True)

    def onRightClickWrapper(self, x, y):
        return lambda Button: self.onRightClick(self.tiles[x][y], True)

    def onClick(self, tile, human = False):
        if self.startTime == None:
            self.startTime = datetime.now()

        if tile["state"] == STATE_CLICKED:
            return
        
        if tile["isMine"] == True:
            self.gameOver(False)
            return
        
        if human:
            self.player.KB.add(Clause((Literal(tile["id"], True),)))

        tile["button"].config(image = self.images["numbers"][tile["mines"]])
        tile["state"] = STATE_CLICKED
        self.clickedCount += 1

        if self.clickedCount == (SIZE_X * SIZE_Y) - self.mines and self.correctFlagCount == self.mines:
            self.gameOver(True)

    def onRightClick(self, tile, human = False):
        if self.startTime == None:
            self.startTime = datetime.now()

        # if not clicked
        if tile["state"] == STATE_DEFAULT:
            tile["button"].config(image = self.images["flag"])
            tile["state"] = STATE_FLAGGED
            tile["button"].unbind(BTN_CLICK)
            # if a mine
            if tile["isMine"] == True:
                self.correctFlagCount += 1
            
            if human:
                self.player.KB.add(Clause((Literal(tile["id"], False),)))

            self.flagCount += 1
            self.refreshLabels()
            if self.clickedCount == (SIZE_X * SIZE_Y) - self.mines and self.correctFlagCount == self.mines:
                self.gameOver(True)
        # if flagged, unflag
        elif tile["state"] == STATE_FLAGGED:
            if tile["isMine"]:
                tile["button"].config(image = self.images["mine"])
            else:
                tile["button"].config(image = self.images["plain"][tile["mines"]])
            tile["state"] = STATE_DEFAULT
            tile["button"].bind(BTN_CLICK, self.onClickWrapper(tile["coords"]["x"], tile["coords"]["y"]))
            if tile["isMine"] == True:
                self.correctFlagCount -= 1
            self.flagCount -= 1
            self.refreshLabels()

### END OF CLASSES ###

def main():
    # create Tk instance
    window = Tk()
    # set program title
    window.title("Minesweeper")
    # create game instance
    minesweeper = Minesweeper(window)
    # run event loop
    window.mainloop()

if __name__ == "__main__":
    main()
