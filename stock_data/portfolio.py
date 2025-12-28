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


    def __init__(self, stock_data, max_price_per_share, starting_balance, max_equity_days, is_portfolio_file, is_back_testing):

        self.stock_data = stock_data
        self.max_price_per_share = max_price_per_share
        self.starting_balance = starting_balance
        self.max_equity_days = max_equity_days
        self.current_balance = starting_balance
        self.pf_data = []
        self.performance = []
        self.is_portfolio_file = is_portfolio_file
        self.is_back_testing = is_back_testing



    def _unique_dates(self, df):
        date_list = df['trading_date'].unique()
        date_list.sort()
        return date_list
    
    def _stock_criteria(self):


        df = self.stock_data
        df = df.loc[df['ticker'].isin(list(df['ticker'].unique()))]
        df = df.loc[(df['close_price']<= self.max_price_per_share)&
                    (~df['yoy_change'].isna())&
                    (df['probability']<.25)&
                    (df['close_price']<df['upper_band'])&
                    (df['close_price']>df['lower_band'])&
                    (df['macd_line'] > df['macd_signal_line'])]
        
        if ~self.is_back_testing:
            
            df = df.loc[df['trading_date']==df['trading_date'].max()]

        return df
    
    def _stock_date_criteria(self,d):

        #confirm the stocks that meet the necessary
        #buying criteria also have all the dates
        #we don't want to analyze stocks that have missing data
        trading_window = self.stock_data.copy()
        trading_window['trading_date'] = pd.to_datetime(trading_window['trading_date'])
        trading_window = trading_window.loc[(trading_window['trading_date'] >= datetime.strptime(d,"%Y-%m-%d")) & 
                                            (trading_window['trading_date'] <= datetime.strptime(d, "%Y-%m-%d")+ timedelta(days = self.max_equity_days))  ]
        stock_count = trading_window['trading_date'].unique().size
        stock_count_df = trading_window.groupby(by=['ticker'])['trading_date'].count().reset_index()
        stock_count_df.rename(columns={'trading_date':'date_count'}, inplace=True)
        stock_count_df = stock_count_df.loc[stock_count_df['date_count']==stock_count]
        
        return stock_count_df['ticker'].to_list()



    def update_portfolio(self):

        #if the portfolio_file is true
        #then we have a starting portfolio file
        if self.portfolio_file:
            try:
                s3 = s3_connector()
                s3.download_file('stock-bucket-01','performance','performance.csv')
                portfolio_data = pd.read_csv('performance.csv', usecols=['ticker', 'trading_date','close_price', 
                                                                            'probability', 'moving_average',
                                                                            'projected_sell_date', 'sold_price',
                                                                            'stock_cost', 'shares_to_purchase',
                                                                            'macd_line', 'macd_signal_line',
                                                                            'sector', 'exchange', 'asset_type'
                                                                            ])
                self.pf_data = portfolio_data.to_list()
            except Exception as e:
                print (e)


        matching_criteria_df = self._stock_criteria()
        sell_dates = self._unique_dates(self.stock_data)
        #sell_dates = [x for x in sell_dates if int(x[:4]) == 2025]
        buy_dates = self._unique_dates(matching_criteria_df)
        matching_criteria_df.sort_values(by=['trading_date', 'yoy_change','probability'], ascending=[True, False, False], inplace=True)
        for d in sell_dates:

            #if  datetime.strptime(d, "%Y-%m-%d").year == 2003:
                #print('found')
                #performance_df = pd.DataFrame(self.performance)
                #performance_df.to_csv('performance.csv', index=False,mode='w')

            df = matching_criteria_df.loc[matching_criteria_df['trading_date']==d].copy()
            if df.empty:
                print(f"The current date is {d}")
                continue
            else:
                df = df.loc[df['ticker'].isin(self._stock_date_criteria(d))]
            print(f"The current date is {d}")

            #check if we have any stocks to see first
            #i.e. do we have any stocks in our portfolio
            if self.pf_data:
                stocks_to_sell_df = self.stock_data.loc[self.stock_data['trading_date']==d]
                stocks_to_sell_df = stocks_to_sell_df.rename(columns={'close_price':'sold_price'})
                list_of_stocks = [d['ticker'] for d in self.pf_data]
                stocks_to_sell_df = stocks_to_sell_df.loc[stocks_to_sell_df['ticker'].isin(list_of_stocks)]
                self._sell_stock(self.pf_data, stocks_to_sell_df,d, .05)

            remaining_balance = self._get_balance()
            
            if df.empty:
                continue
            else:
                if d in buy_dates:
                    if self.pf_data:
                        threshold_df = pd.DataFrame(data=self.pf_data)
                        threshold_df = threshold_df.groupby(by=['sector'])['stock_cost'].sum().reset_index()
                        threshold_df['pct_of_account'] = threshold_df['stock_cost'] / self.starting_balance
                        threshold_df = threshold_df.loc[threshold_df['pct_of_account']>.25]
                        df = df.loc[~df['sector'].isin(threshold_df['sector'].to_list())]
                    stocks_added = self._add_stock(df,remaining_balance, self.pf_data)
                    if stocks_added: 
                            self.pf_data.extend(stocks_added)
                            stock_purchase_cost = sum(row['stock_cost'] for row in stocks_added)
                            self._withdraw(stock_purchase_cost)
            
        return pd.DataFrame(self.performance)
    
    def _add_stock(self,df, balance, cp):

        #check to see if stock is already in the portfolio
        #we don't add existing stocks to the portfolio
        stocks_to_buy = df.copy()
        if cp:
            current_portfolio = [row['ticker'] for row in cp]
            stocks_to_buy = stocks_to_buy.loc[~stocks_to_buy['ticker'].isin(current_portfolio)]
        stocks_to_buy['shares_to_purchase'] = np.floor(stocks_to_buy['close_price'].apply(lambda x: self.max_price_per_share / x ))
        stocks_to_buy['stock_cost'] = np.round(stocks_to_buy['shares_to_purchase'] * stocks_to_buy['close_price'],2)
        remaining_balance = self._get_balance()
        stocks_to_buy['cumlative_stock_cost'] = stocks_to_buy['stock_cost'].cumsum()
        
        #we return the list of stocks we can 
        #afford to purchase with our availble balance
        try:
            stocks_to_buy.loc[stocks_to_buy['cumlative_stock_cost'] <= remaining_balance,'isPurchased'] = True
        except Exception as e:
            print(f"Unable to find any stocks to buy. Here is the exception: {e}" )
            return list()
        print(self._get_balance())
        stocks_to_buy = stocks_to_buy.loc[stocks_to_buy['isPurchased']==True].copy()
        
        if not stocks_to_buy.empty:
            stocks_to_buy['projected_sell_date'] = pd.to_datetime(stocks_to_buy['trading_date']) + timedelta(days = self.max_equity_days)
            print(stocks_to_buy[['trading_date', 'ticker', 'close_price',
                   'probability', 'moving_average','projected_sell_date', 'stock_cost',
                   'shares_to_purchase']].head(10))
            return stocks_to_buy[['trading_date', 'ticker', 'close_price',
                   'probability', 'moving_average','projected_sell_date', 'stock_cost',
                   'shares_to_purchase', 'macd_diff', 'macd_line', 'macd_signal_line',
                   'sector', 'exchange', 'asset_type']].to_dict(orient='records')
    
    def _sell_stock(self,current_portfolio, daily_data,current_date, exit_pct):

        #return the stocks that don't have a project sell date less
        #than the current data aka that haven't hit the time
        #record to sell the stocks
        daily_data.rename(columns={'macd_line':'sold_macd_line', 'macd_signal_line':'sold_macd_signal_line'}, inplace=True)
        daily_data = daily_data.to_dict(orient='records')
        daily_data_updated = [{key: d[key] for key in ['ticker', 'upper_band', 'lower_band', 'sold_price', 'sold_macd_line', 'sold_macd_signal_line'] if key in d} for d in daily_data]
        current_portfolio_updated = [{key: d[key] for key in ['ticker', 'trading_date','close_price', 
                                                              'probability', 'moving_average',
                                                              'projected_sell_date', 'sold_price',
                                                              'stock_cost', 'shares_to_purchase',
                                                              'macd_line', 'macd_signal_line',
                                                              'sector', 'exchange', 'asset_type'] if key in d} for d in current_portfolio]
        updated_portfolio = self._merge_list(current_portfolio_updated, daily_data_updated)

        #sell the stock when current date is greater than the project sell date
        #sell the stock when the sold price (projected sold price) is less than the lower band
        #sell the stock when the sold price (projected sold price) is greater than 5% or above the upper band
        stocks_to_sell = [x for x in updated_portfolio if (x['projected_sell_date'].date() <= datetime.strptime(current_date, "%Y-%m-%d").date()) or
                          (x['sold_price'] <= x['lower_band']) or (x['sold_price'] >= x['upper_band'])
                          or (abs(((x['sold_price'] - x['close_price'])/x['close_price'])) >= exit_pct) 
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
            daily_revenue = sum([row['sold_price'] * row['shares_to_purchase'] for row in stocks_to_sell_updated])
            daily_pct = (daily_revenue - amount_sold) / amount_sold
            print(f"For {current_date} the portfolio earned {(daily_revenue - amount_sold):.2f} in cash and the pct of return was {daily_pct:.2%}")
            [self.performance.append(row) for row in stocks_to_sell_updated]


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






    