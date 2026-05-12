Three-Address Code
==================================================
x = 5
printf x
y = 3.14
alloc list[5]
list[0] = 10
list[1] = 20
t0 = list[0]
t1 = list[1]
t2 = t0 + t1
list[2] = t2
sum = 0
i = 0
L0:
t3 i 5 LT
ifFalse t3 goto L1
t4 = sum + i
sum = t4
t5 = i
t6 = i + 1
i = t6
goto L0
L1:
printf sum
t7 = y * 2.0
result = t7
printf result
score = 85
t8 score 90 GE
ifFalse t8 goto L2
printf score
goto L3
L2:
grade = 2
printf grade
L3:
n = 5
fact = 1
L4:
t9 n 1 GT
ifFalse t9 goto L5
t10 = fact * n
fact = t10
t11 = n - 1
n = t11
goto L4
L5:
printf fact
