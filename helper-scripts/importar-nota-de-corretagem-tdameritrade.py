import sys
import os

import csv
import re
from decimal import *
from datetime import datetime
from piecash import open_book, ledger, factories, Account, Transaction, Commodity, Split, GnucashException

file_path = sys.argv[1]
gnucash_db_path = sys.argv[2]

# este script necessita das notas de corretagem salvas em csv com o delimitador ';'

def write_to_gnucash(stocks, dividends, transfers):
    with open_book(gnucash_db_path, readonly=False) as book:
        bank_account = book.accounts(name='Conta no TD Ameritrade')

        print("Importing {} stock, {} dividend and {} transfers transactions".format(len(stocks), len(dividends), len(transfers)))

        for stock in stocks:
            symbol = stock['symbol'].upper()
            if ' ' in symbol:
                symbol = symbol.replace(' ', '-')

            try:
                stock_commodity = book.commodities(mnemonic=symbol)
            except KeyError:
                stock_commodity = Commodity(mnemonic=symbol,
                    fullname=symbol,
                    fraction=1,
                    namespace='US',
                    quote_flag=1,
                    quote_source="yahoo_json",
                )
                book.flush()

            try:
                stock_account = book.accounts(commodity=stock_commodity)
            except KeyError:
                parent_account = book.accounts(name='Ações no exterior')

                stock_account = Account(name=symbol,
                    type="STOCK",
                    parent=parent_account,
                    commodity=stock_commodity,
                    placeholder=False,
                )
                book.flush()

            value = Decimal(stock['value'])
            quantity = Decimal(stock['quantity'])
            if value < 0:
                quantity = -quantity

            date = datetime.strptime(stock['date'], "%m/%d/%Y")
            description = stock['description']

            t1 = Transaction(currency=bank_account.commodity,
                description=description,
                post_date=date.date(),
                splits=[
                    Split(value=value, quantity=quantity, account=stock_account),
                    Split(value=-value, account=bank_account)
                ]
            )
            print(ledger(t1))

        book.save()
        
        # TODO: import dividends and transfers
        # TODO: print sold and bought values, dividends values, transfer values


def process_csv(csv_file):

    # read stocks, amounts and prices
    stocks = []
    dividends = []
    transfers = []

    reader = csv.DictReader(csv_file, delimiter = ',', quotechar='"')
    for row in reader:
        date = row['DATE']
        if 'end' in date.lower():
            break

        description = row['DESCRIPTION']
        symbol = row['SYMBOL']
        amount = Decimal(row['AMOUNT'])
        if 'wire' in description.lower():
            transfers.append({
                'date': date,
                'direction': 'incoming' if amount > 0 else 'outgoing',
                'description': description,
                'value': amount
            })
        elif any(x in description.lower() for x in ['bought', 'sold']):
            stocks.append({
                'date': date,
                'description': description,
                'symbol': symbol,
                'quantity': row['QUANTITY'],
                'value': -amount,
            })
        elif any(x in description.lower() for x in ['dividend', 'w-8']):
            dividends.append({
                'date': date,
                'description': description,
                'symbol': symbol,
                'value': amount
            })
        else:
            raise Exception("Unrecognizable row")

    return (stocks, dividends, transfers)


with open(file_path,  newline='') as csv_file:
    stocks, dividends, transfers = process_csv(csv_file)
    write_to_gnucash(stocks, dividends, transfers)
