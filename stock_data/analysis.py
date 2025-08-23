import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from scipy.stats import norm

class analysis():
    def __init__(self, df):
        self.data = df

    def add_columns(self, r_periods):

        self.data.sort_values(by=['Ticker', 'Trading_Date'], inplace=True)
        self.data['Previous_Price'] = self.data.groupby(by=['Ticker'])['Close_Price'].shift(periods=1)
        self.data['Last_Year_Price'] = self.data.groupby(by=['Ticker'])['Close_Price'].shift(periods=-1) #update to 252 with the real data
        self.data['YoY_Change'] = (self.data['Close_Price'] - self.data['Last_Year_Price']) / self.data['Last_Year_Price']
        self.data['Daily_Return'] = np.log(self.data['Close_Price'] / self.data['Previous_Price'])
        self.data['Stdev'] = self.data.groupby(by=['Ticker'])['Close_Price'].transform(lambda x: x.rolling(r_periods, min_periods=r_periods).std())
        self.data['Moving_Average'] = self.data.groupby(by=['Ticker'])['Close_Price'].transform(lambda x: x.rolling(r_periods, min_periods=r_periods).mean()).round(decimals=2)
        self.data['Upper_Band'] = self.data['Moving_Average'] + (self.data['Stdev'] * 2)
        self.data['Lower_Band'] = self.data['Moving_Average'] - (self.data['Stdev'] * 2)
        self.data.loc[(self.data['YoY_Change']>=0) & (self.data['Moving_Average'].notna()) ,'Testable'] = 1
        self.data.loc[self.data['Stdev']!=np.nan, 'Z_Score'] = (self.data['Close_Price'].round(2) - self.data['Moving_Average'].round(2)) / self.data['Stdev']
        self.data['Probability'] = norm.cdf(self.data['Z_Score'])

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
