def successorFunction(Qcount, arr):
    pass


def genArray(x,y,arr):
    t = [[0]*n for i in range(m)]
    for i in range(n):
        t[i][y] = 1
        t[x][i] = 1
        a = x+i
        if a >= n:
            a = x 
        b = x-i
        if b < 0:
            b = x
        c = y+i
        if c >= m:
            c = y 
        d = y-i
        if d < 0:
            d = y
        t[a][c] = 1
        t[a][d] = 1 
        t[b][c] = 1
        t[b][d] = 1
    t[x][y] = 2


    for i in t:
        print(i)
    print()    
    
    return t

def addArray(arr1, arr2):
    #Assumes same size arrays,
    t = [[0]*n for i in range(m)]
    for i in range(len(arr1)):
        for j in range(len(arr1[0])):
            t[i][j] = arr1[i][j] + arr2[i][j]

    return t
            

def printArr(arr):
    for i in arr:
        print(i)




n = 6
m = 6
t = [[0]*n for i in range(m)]

printArr(addArray(genArray(3,3,t), genArray(0,1,t)))
#Add into the next possible 0,g

stack = []
stack.append((0,0))
queenCount = 0
while queenCount != n:
    for i in range(n):
        for j in range(m):
            if t[i][j] == 0:
                genArray(i,j,t)


    queenCount += 1
    break


