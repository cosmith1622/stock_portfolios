import pandas as pd
import numpy as np
import os
import uuid
from stock_data.stock_data import stock_data
from stock_data.stock_data_connector import stock_data_connector
from stock_data.s3_connector import s3_connector
from datetime import date, timedelta
from stock_data.analysis import analysis
from stock_data.portfolio_data import portfolio_data


"""
    Step 1 Get the latest stock date in the database.
    If that stock exist in Step 2, we will get the 
    latest information for the stock.

"""
pdata = portfolio_data()
data =  pdata.get_latest_stock_data('stock-bucket-01')

"""
    Step 2 get updated stock information for the stocks
    that should be evaluated based on the conditions in the 
    find_equities method and create a csv.  Then push the 
    csv into an s3 bucket

"""

df = pdata.get_latest_equities_data('stock-bucket-01')


"""

Step 4
create a list of all the stocks in the database and
their last date of data and append it to the new stocks
with their first date of data we will collect from

create a unqiue list of start dates for pulling
new stock data.  We will later use this to group
stocks with the same starting point to pull data
in parallel based on starting point

Then push the data into an s3 bucket

"""

pdata.get_stock_data(data,df,'stock-bucket-01')



"""
    Push the new stock data into the redshift db

"""
pdata.insert_data('stock-bucket-01')





"""
def create_portfolio(data):
     results = []
     for item in data:
          guid = uuid.uuid4()
          for row in item:
               results.append(np.append(row,guid))
     return results

def add_shares(data,portfolio_amount, portfolio_size):
        even_size = portfolio_amount / portfolio_size
        obj = [row for row in data if row[2] <= even_size]
        if portfolio_size != len(obj):
            try:
                even_size = portfolio_amount / len(obj)
                results = [np.append(row,even_size // row[2]) for row in obj]
                return results
            except ZeroDivisionError as err:
                 #print(err)
                 return
        else:
            results = [np.append(row,even_size // row[2]) for row in obj]
            return results

def remove_stocks(data, amount):
    for index,row in data.iterrows():
        if row['adjclose_price'] > amount:
            print(row.index)
            data.drop(index=index, inplace=True)
    return data

def max_stock_dates(cursor):
     df = pd.DataFrame(cursor.execute("Select max(trading_date), ticker From dev.public.stock_history group by ticker"))
     return df

def get_file_size_in_mb(file_path):
    
    size_in_bytes = os.path.getsize(file_path)
    size_in_mb = size_in_bytes / (1024 * 1024)
    return size_in_mb

#df = pd.read_csv('../opm_march_2024/stock_data.csv')
#cursor.execute(f"Select * From dev.public.stock_history where trading_date >= '2000-01-01'")
#df = pd.DataFrame(cursor.fetchall(), columns=['trading_date', 'open_price', 'high_price', 'low_price', 'close_price',
#                                              'adjclose_price', 'ticker', 'volume'])
#conn.close()
df = pd.read_csv('../opm_march_2024/aws_stock_data')
df.drop(columns=['Unnamed: 0'], inplace=True)
df['previous_price'] = df.groupby(by=['ticker'])['adjclose_price'].shift(periods=1)
df['month_prior_price'] = df.groupby(by=['ticker'])['adjclose_price'].shift(periods=20)
df['month_next_price'] = df.groupby(by=['ticker'])['adjclose_price'].shift(periods=-20)
print(df.head(42))
df['daily_return'] = np.log(df['adjclose_price'] / df['previous_price'])
df['daily_return_mva'] = df.groupby(by=['ticker'])['daily_return'].transform(lambda x: x.rolling(20, min_periods=20).sum())
df['annual_return'] = df['daily_return_mva'] * (252/5)
df['stdev_prices'] = df.groupby(by=['ticker'])['adjclose_price'].transform(lambda x: x.rolling(20, min_periods=20).std())
df['annual_stdev_returns'] = df.groupby(by=['ticker'])['daily_return'].transform(lambda x: x.rolling(20, min_periods=20).std())
df['annual_stdev_returns'] = df['annual_stdev_returns'] * (252 ** .5)
print(df.tail(6))
df['moving_average'] = df.groupby(by=['ticker'])['adjclose_price'].transform(lambda x: x.rolling(20, min_periods=20).mean()).round(decimals=2)
df['upper_band'] = df['moving_average'] + (df['stdev_prices'] * 2)
df['lower_band'] = df['moving_average'] - (df['stdev_prices'] * 2)
df['z_score_prices'] = df.apply(lambda x: (x['adjclose_price'] - x['moving_average']) / x['stdev_prices'], axis = 1)

print(df.tail(6))
df = remove_stocks(df, 1000)
df.sort_values(by='trading_date', ascending=False, inplace=True)
dates = df['trading_date'].unique()

results = []
for d in dates:
    daily_df = df[df['trading_date']== d]
    #print(daily_df['adjclose_price'])
    portfolio = np.array(daily_df[['trading_date','ticker', 'adjclose_price']])
    #print(portfolio[0])
    #print(len(portfolio[:2]))
    #print(portfolio[:2])
    for num in range(len(daily_df['ticker'].unique())):
        #print(portfolio[:num+1])
        results.append(add_shares(portfolio[:num+1], 1000,num+1))

results = [x for x in results if x != None]
results = create_portfolio(results)
portfolio_options = pd.DataFrame(data=results,columns=['Date', 'symbol', 'price', 'shares', 'guid'])
portfolio_options = portfolio_options.merge(right=df, how='left', left_on=['Date', 'symbol'], right_on=['trading_date', 'ticker'])
print(portfolio_options.columns)
portfolio_options = portfolio_options[['Date', 'guid','symbol',
                                       'adjclose_price', 'month_prior_price', 'shares',
                                       'month_next_price','annual_stdev_returns']]
portfolio_options['pct_change'] = (portfolio_options['adjclose_price'] - portfolio_options['month_prior_price']) / portfolio_options['month_prior_price']
portfolio_options['future_pct_change'] = (portfolio_options['month_next_price'] - portfolio_options['adjclose_price']) / portfolio_options['adjclose_price']
portfolio_options['stock_size'] = portfolio_options['adjclose_price'] * portfolio_options['shares']
portfolio_options['portfolio_size'] = portfolio_options.groupby(by=['guid'])['stock_size'].transform('sum')
print(portfolio_options.head())
portfolio_options['pct_size'] = portfolio_options['stock_size'] / portfolio_options['portfolio_size']
print(portfolio_options.head())
portfolio_options['stock_return'] = portfolio_options['pct_change'] * portfolio_options['pct_size']
portfolio_options['future_stock_return'] = portfolio_options['future_pct_change'] * portfolio_options['pct_size']
portfolio_options['annual_stdev_returns_size'] = portfolio_options['annual_stdev_returns'] *  portfolio_options['pct_size']
portfolio_options['portfolio_return'] =  portfolio_options.groupby(by=['guid'])['stock_return'].transform('sum')
portfolio_options['future_portfolio_return'] =  portfolio_options.groupby(by=['guid'])['future_stock_return'].transform('sum')
portfolio_options['portfolio_annual_stdev'] = portfolio_options.groupby(by=['guid'])['annual_stdev_returns_size'].transform('sum')
print(portfolio_options.columns)
portfolio_options = portfolio_options[['Date', 'guid', 'symbol',
                                       'adjclose_price', 'month_prior_price', 'future_portfolio_return',
                                       'shares','portfolio_return', 'portfolio_annual_stdev',
                                       'month_next_price']]
portfolio_options = portfolio_options[portfolio_options['Date'].isin(['2024-02-01', '2024-03-01', '2024-04-01',
                                                                      '2024-05-01', '2024-06-01', '2024-07-01',
                                                                      '2024-08-01', '2024-09-01', '2024-10-01',
                                                                      '2024-11-01'])]
print(portfolio_options.head())
portfolio_options.drop_duplicates(subset=['Date', 'symbol', 'adjclose_price',
                                          'shares','month_prior_price', 'future_portfolio_return',
                                          'portfolio_return', 'portfolio_annual_stdev',
                                          'month_next_price'], inplace=True)
portfolio_options.to_csv('portfolio_data.csv')
list_of_data = [{'url':'../opm_march_2024/DTloc.txt', 'data_set_name':'location', 
                 'custom_columns':{'LocTYPT':'country_name', 'LOCT':'state_territory_name',
                                   'LOCTYP': 'country_id', 'LOC': 'state_territory_id'
                                   }
                },
                 {'url':'../opm_march_2024/DTwrksch.txt','data_set_name':'word_schedule',
                 'custom_columns':{}
                 }
                ]
#opm_data = opm_warehouse()
#for report in list_of_data:
#    object = opm_data.add_dataset(report['url'],report['data_set_name'])
#    opm_data.rename_columns(object, report['custom_columns'])
#    print(object.columns)
#data = opm_data.get_opm_data()
#print(data[0].columns)
#opm_data.rename_columns([{'LocTYPT':'country_name', 'LOCT':'state_territory_name',
#                         'LOCTYP': 'country_id', 'LOC': 'state_territory_id'}])
#df1 = pd.read_csv("../opm_march_2024/DTwrksch.txt")

#opm_data.add_dataset(df1, name='work_schedule')
#data = opm_data.get_opm_data()
#office_schedules = data[1]
#print(data[0].head())

"""