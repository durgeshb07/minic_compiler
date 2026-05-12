
int x = 5;
printf(x);

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
printf(sum);

float result = y * 2.0;
printf(result);

int score = 85;
if (score >= 90) {
    printf(score);
} else {
    int grade = 2;
    printf(grade);
}

int n = 5;
int fact = 1;
while (n > 1) {
    fact = fact * n;
    n = n - 1;
}
printf(fact);