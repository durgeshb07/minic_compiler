Three-Address Code
==================================================
x = 5
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
t5 = i + 1
i = t5
goto L0
L1:
print sum
t6 = y * 2.0
result = t6
print result
score = 85
t7 score 90 GE
ifFalse t7 goto L2
print score
goto L3
L2:
grade = 2
print grade
L3:
n = 5
fact = 1
L4:
t8 n 1 GT
ifFalse t8 goto L5
t9 = fact * n
fact = t9
t10 = n - 1
n = t10
goto L4
L5:
print fact
