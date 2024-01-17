from turtle import *

Canvas = Turtle()


i0 = 1
i1 = 1
for i in range(1,100):
    Canvas.right(i0 / i1 * 100)
    Canvas.forward(i0)
    temp = i1
    i1 = i1 + i0
    i0 = temp
    print(i0)

Canvas.screen.mainloop()



def WriteFinger():
    pass


"""
class Player: 
    def __init__(self, name):
        self.hand1 = 1
        self.hand2 = 1
        self.PlayerName = name


def main():
    player1 = Player("name") 
    player2 = Player("name2")


    pass

def attack(finger1, finger2):
    finger2 += finger1
    return
def choosePlayers():
    pass

def randomNumber():
    pass
"""


