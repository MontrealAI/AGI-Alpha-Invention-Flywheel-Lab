def withdraw(balance, amount):
    return balance - amount if 0 <= amount <= balance else balance
