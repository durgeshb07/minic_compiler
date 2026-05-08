// test_program.mc  —  exercises all Mini-C features

int x = 5;
float y = 3.14;
int list[5];

list[0] = 10;
list[1] = 20;
list[2] = list[0] + list[1];

int sum = 0;
int i;
for (i = 0; i < 5; i++) {
    sum = sum + i;
}
print(sum);

float result = y * 2.0;
print(result);

int score = 85;
if (score >= 90) {
    print(score);
} else {
    int grade = 2;
    print(grade);
}

int n = 5;
int fact = 1;
while (n > 1) {
    fact = fact * n;
    n = n - 1;
}
print(fact);