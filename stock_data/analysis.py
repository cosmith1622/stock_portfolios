import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from scipy.stats import norm
from stock_data import stock_data_connector
import os

class analysis:
    def __init__(self):
        self.data = []

    def add_columns(self, r_periods):

        df = pd.read_csv('latest_data.csv', names = ['trading_date', 'ticker', 'open_price', 'high_price',
                                                   'low_price', 'close_price', 'adjclose_price', 'volume'
                                                   ])
        df = df.loc[df['trading_date']!='0'].copy()
        df.sort_values(by=['ticker', 'trading_date'], inplace=True)
        df['previous_price'] = df.groupby(by=['ticker'])['close_price'].shift(periods=1)
        df['last_year_price'] = df.groupby(by=['ticker'])['close_price'].shift(periods=r_periods) #update to 252 with the real data
        print(df['last_year_price'])
        df['yoy_change'] = (df['close_price'] - df['last_year_price']) / df['last_year_price']
        df.loc[df['yoy_change']>=.25,'above_25_percent'] = True

        #probability columns
        df['daily_return'] = np.log(df['close_price'] / df['previous_price'])
        df['stdev'] =df.groupby(by=['ticker'])['close_price'].transform(lambda x: x.rolling(20, min_periods=20).std())
        df['moving_average'] = df.groupby(by=['ticker'])['close_price'].transform(lambda x: x.rolling(20, min_periods=20).mean()).round(decimals=2)
        df['upper_band'] = df['moving_average'] + (df['stdev'] * 2)
        df['lower_band'] = df['moving_average'] - (df['stdev'] * 2)
        df.loc[(df['yoy_change']>=0) & (df['moving_average'].notna()) ,'Testable'] = 1
        df.loc[df['stdev']!=np.nan, 'z_score'] = (df['close_price'].round(2) - df['moving_average'].round(2)) / df['stdev']
        df['probability'] = norm.cdf(df['z_score'])

        #macd columns
        df['12_day_ema'] = df['close_price'].ewm(span=12, adjust=False, min_periods=12).mean()
        df['26_day_ema'] = df['close_price'].ewm(span=26, adjust=False, min_periods=26).mean()
        df['macd_line'] = df['12_day_ema'] - df['26_day_ema']
        df['macd_signal_line'] = df['macd_line'].ewm(span=9, adjust=False, min_periods=9).mean()
        df['macd_diff'] =  df['macd_line'] - df['macd_signal_line']
        return df

    def get_data(self):
        return self.data

    def fib_analysis(self):

        self.data['max_close_30_days'] = self.data.groupby('ticker')['close'].rolling(30).max().reset_index(0,drop=True)
        self.data['min_close_30_days'] = self.data.groupby('ticker')['close'].rolling(30).min().reset_index(0,drop=True)
        self.data['vertical_distance'] = self.data['max_close_30_days'] - self.data['min_close_30_days']
        self.data['23_ratio'] = self.data['vertical_distance'] / .23
        self.data['50_ratio'] = self.data['vertical_distance'] / .50
        self.data['62_ratio'] = self.data['vertical_distance'] / .62
        print(self.data.tail())
        print('cole')

    def get_stock_data(self):

        """
            grab the latest date we have for each stock
            check to see if the data is already in s3, if not go
            to the database pull the data.
            Then upload the data to the s3 bucket
            and return the data to the caller

        """
        
        try:
            sdc = stock_data_connector()
            conn = sdc.connector.connect(host=os.environ['db_host'],
                                        database=os.environ['db_database'],
                                        port=os.environ['db_port'], 
                                        user=os.environ['db_user'], 
                                        password=os.environ['db_password'])
            cursor = conn.cursor()
            cursor.execute("""with data as (

                                    Select ticker
                                    From stock_history
                                    where trading_date = (Select max(trading_date) from stock_history)
                                    Group by ticker

                            )
                            Select *
                            From stock_history
                            where ticker in (Select ticker from data)
                            and trading_date >= '2000-01-01'
            """)
            data = cursor.fetchall()
            df = pd.DataFrame(data)
            df.to_csv('latest_data.csv', index=False, mode = 'w')

        except Exception as e:
            print(e)
            raise e
        finally:
            if conn != None:
                conn.close()
                sdc = None
            return df
