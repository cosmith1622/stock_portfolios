import pandas as pd
import numpy as np
import os
from stock_data import stock_data
from stock_data import stock_data_connector
from stock_data import s3_connector
from datetime import date, timedelta, datetime
import boto3
from botocore.exceptions import ClientError

class portfolio:


    def __init__(self, stock_data, max_price_per_share, starting_balance, max_equity_days):

        self.stock_data = stock_data
        self.max_price_per_share = max_price_per_share
        self.starting_balance = starting_balance
        self.max_equity_days = max_equity_days
        self.current_balance = starting_balance
        self.pf_data = []
        self.performance = []



    def _unique_dates(self, df):
        date_list = df['trading_date'].unique()
        date_list.sort()
        return date_list
    
    def _stock_criteria(self):
        df = self.stock_data.loc[self.stock_data['above_25_percent']==True]
        df = df.loc[df['ticker'].isin(list(df['ticker'].unique()))]
        df = df.loc[(df['close_price']<= self.max_price_per_share)&
                    (~df['yoy_change'].isna())&
                    (df['probability']>.5)&
                    (df['close_price']<df['upper_band'])&
                    (df['close_price']>df['lower_band'])]
        return df


    def update_portfolio(self):

        df = self._stock_criteria()
        unique_dates = self._unique_dates(df)
        df.sort_values(by=['trading_date', 'yoy_change','probability'], ascending=[True, False, False], inplace=True)
        for d in unique_dates:
            
            if  datetime.strptime(d, "%Y-%m-%d").year == 2010:
                print('found')
            df = df.loc[df['trading_date']==d].copy()

            #check if we have any stocks to see first
            #i.e. do we have any stocks in our portfolio
            if self.pf_data:
                stocks_to_sell_df = self.stock_data.loc[self.stock_data['trading_date']==d]
                stocks_to_sell_df = stocks_to_sell_df.rename(columns={'close_price':'sold_price'})
                list_of_stocks = [d['ticker'] for d in self.pf_data]
                stocks_to_sell_df = stocks_to_sell_df.loc[stocks_to_sell_df['ticker'].isin(list_of_stocks)]
                self._sell_stock(self.pf_data, stocks_to_sell_df,d, .05)

            remaining_balance = self._get_balance()
            stocks_added = self._add_stock(df,remaining_balance, self.pf_data)
            if stocks_added:
                    self.pf_data.extend(stocks_added)
                    stock_purchase_cost = sum(row['stock_cost'] for row in self.pf_data)
                    self._withdraw(stock_purchase_cost)
            """
            #check to see if we have stock data for that date
            #and the portfolio is empty
            #if both are true we don't have stocks to
            #evaulate for purhcase or to sell
            if df.empty and not self.pf_data:
                continue
                
            else:
                if not self.pf_data:
                    remaining_balance = self._get_balance()
                    stocks_added = self._add_stock(df,remaining_balance, self.pf_data)
                    if stocks_added:
                        self.pf_data.extend(stocks_added)
                    stock_purchase_cost = sum(row['stock_cost'] for row in self.pf_data)
                    self._withdraw(stock_purchase_cost)
                else:
                    #return the most recent prices 
                    #for the stocks in our portfolio
                    #we will use the data to determine if we should sell
                    stocks_to_sell_df = self.stock_data.loc[self.stock_data['trading_date']==d]
                    stocks_to_sell_df = stocks_to_sell_df.rename(columns={'close_price':'sold_price'})
                    list_of_stocks = [d['ticker'] for d in self.pf_data]
                    stocks_to_sell_df = stocks_to_sell_df.loc[stocks_to_sell_df['ticker'].isin(list_of_stocks)]
                    self._sell_stock(self.pf_data, stocks_to_sell_df,d, .05)
                    remaining_balance = self._get_balance()
                    stocks_added = self._add_stock(df,remaining_balance, self.pf_data)
                    if stocks_added:
                        self.pf_data.extend(stocks_added)
            remaining_balance = self._get_balance()
            """
        return df
    
    def _add_stock(self,df, balance, cp):

        #check to see if stock is already in the portfolio
        #we don't add existing stocks to the portfolio
        if cp:
            current_portfolio = [row['ticker'] for row in cp]
            df = df.loc[~df['ticker'].isin(current_portfolio)]
        df['shares_to_purchase'] = np.floor(df['close_price'].apply(lambda x: self.max_price_per_share / x ))
        df['stock_cost'] = np.round(df['shares_to_purchase'] * df['close_price'],2)
        remaining_balance = self._get_balance()
        df['cumlative_stock_cost'] = df['stock_cost'].cumsum()
        
        #we return the list of stocks we can 
        #afford to purchase with our availble balance
        df.loc[df['cumlative_stock_cost'] <= remaining_balance,'isPurchased'] = True
        print(self._get_balance())
        df = df.loc[df['isPurchased']==True].copy()
        
        if not df.empty:
            df['projected_sell_date'] = pd.to_datetime(df['trading_date']) + timedelta(days = self.max_equity_days)
            print(df[['trading_date', 'ticker', 'close_price',
                   'probability', 'projected_sell_date', 'stock_cost',
                   'shares_to_purchase']].head(10))
            return df[['trading_date', 'ticker', 'close_price',
                   'probability', 'projected_sell_date', 'stock_cost',
                   'shares_to_purchase']].to_dict(orient='records')
    
    def _sell_stock(self,current_portfolio, daily_data,current_date, exit_pct):

        #return the stocks that don't have a project sell date less
        #than the current data aka that haven't hit the time
        #record to sell the stocks

        daily_data = daily_data.to_dict(orient='records')
        daily_data_updated = [{key: d[key] for key in ['ticker', 'upper_band', 'lower_band', 'sold_price'] if key in d} for d in daily_data]
        current_portfolio_updated = [{key: d[key] for key in ['ticker', 'close_price', 
                                                              'projected_sell_date', 'sold_price',
                                                              'stock_cost', 'shares_to_purchase'] if key in d} for d in current_portfolio]
        updated_portfolio = self._merge_list(current_portfolio_updated, daily_data_updated)

        #sell the stock when current date is greater than the project sell date
        #sell the stock when the sold price (projected sold price) is less than the lower band
        #sell the stock when the sold price (projected sold price) is greater than 5% or above the upper band
        stocks_to_sell = [x for x in updated_portfolio if (x['projected_sell_date'].date() <= datetime.strptime(current_date, "%Y-%m-%d").date()) or
                          (x['sold_price'] <= x['lower_band']) or (x['sold_price'] >= x['upper_band'])
                          or (((x['sold_price'] - x['close_price'])/x['close_price']) >= exit_pct) 
                          ]
        #if we have stocks to sell
        #we need to remove them from the portfolio
        #and update our balance 
        if stocks_to_sell: 
            list_of_stocks_to_sell = [s[key] for key in ['ticker'] for s in stocks_to_sell]
            amount_sold = sum(row['stock_cost'] for row in stocks_to_sell)
            self._add_balance(amount_sold)
            self.pf_data = [x for x in current_portfolio if x['ticker'] not in list_of_stocks_to_sell]
            stocks_to_sell_updated = [{**x, 
                                       'actual_sell_date':datetime.strptime(current_date, "%Y-%m-%d").date(),
                                       'cash return':((x['sold_price'] - x['close_price']) * x['shares_to_purchase']),
                                       'pct return':(x['sold_price'] - x['close_price']) / (x['close_price'])} for x in stocks_to_sell]
            self.performance.append(stocks_to_sell_updated)
        


    def _merge_list(self, current_portfolio, daily_data):

        updated_list = []
        matching_dict = {item['ticker']: item for item in daily_data}
        for item in current_portfolio:
            matching_value = item['ticker']
            if matching_value in matching_dict:
                merged_item = {**matching_dict[matching_value], **item}
                updated_list.append(merged_item)
        return updated_list


    def _remaining_balance(self):
        self.current_balance = self.starting_balance - self.current_balance
        return self.current_balance
    
    def _get_balance(self):
        return self.current_balance
    
    def _withdraw(self, amount):
        self.current_balance -= amount

    def _add_balance(self, funds):
        self.current_balance += funds
        return self.current_balance






    