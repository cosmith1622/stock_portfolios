import pandas as pd
import numpy as np
from yfinance import Ticker, Tickers, EquityQuery, screen
from typing import Union
from curl_cffi import requests

class stock_data:
    def __init__(self):
        self.stock_data = None
        self.research_equities = None
        self.session = requests.Session(impersonate="chrome")

    def find_equities(self,pagination):

        #create query for stocks, we look for stocks in a given exchange, floor price and 
        #recent peformance
        query = EquityQuery('and', [
                                    EquityQuery('is-in', ['exchange', 'NMS', 'NYQ']),
                                    EquityQuery('lte', ['eodprice',100]),
                                    EquityQuery('gte',["fiftytwowkpercentchange",25])
                                    ]
                        )
        response = screen(query, session=self.session)
        all_data = []
        step = pagination

        #iterate throught the list of equities 
        #return the equities
        for i in range(0,response['total'],step):
            
            if i != 0:

                pagination = pagination + step

            data = response['quotes']
            data = self._get_equities_info(data)
            all_data.extend(data)

            if i < (response['total'] - step):
    
                response = screen(query, offset = pagination, session=self.session)

            else:

                break

        self.research_equities  = pd.DataFrame(all_data)
        return self.research_equities
    
    def _get_equities_info(self, data):
        
        #return data about the equities found 
        #based on the equities that met the requirents of the query
        for equity in data:
            
            try:

                ticker_info = Ticker(equity['symbol'], session=self.session).get_info()
                
                try:
                    equity['sector'] = ticker_info['sector']
                except KeyError:
                    equity['sector'] = None
                    print(f"Equity {equity['symbol']} doens't have sector information")
                try:
                    equity['industy'] = ticker_info['industry']
                except KeyError:
                    equity['industy'] = None
                    print(f"Equity {equity['symbol']} doens't have industry information")

            except Exception as e:
                print(f"Error when tring to get industy and sector data for {equity['symbol']}: {e}")

        return data

    def get_stocks(self, stocks : Union[str, list], **kwargs ):
            print(kwargs)
            try:
                if isinstance(stocks, str):

                    tick = Ticker(stocks)
                    stock_data = tick.history(start=kwargs['start'], auto_adjust=kwargs['auto_adjust'])
                    stock_data.reset_index(inplace=True)

                    self.stock_data = stock_data[['Date', 'Open', 'High', 'Low', 'Close','Volume']]
                    self.stock_data.rename(columns={'Date':'Trading_Date',
                                                    'Open':'Open_Price',
                                                    'Close':'Close_Price',
                                                    'High':'High_Price',
                                                    'Low':'Low_Price'
                                                },
                                           inplace=True
                    )

                else:

                    string_of_stocks = " ".join(stocks)
                    ticks = Tickers(string_of_stocks)
                    stock_data = ticks.download(start=kwargs['start'], 
                                                auto_adjust=kwargs['auto_adjust'], 
                                                threads=kwargs['threads'],                                                
                                                session=self.session)
                    stock_data = self._create_stocks_df(list_of_stocks=stocks, data = stock_data)
                    self.stock_data = stock_data
                    self.stock_data['Trading_Date'] = self.stock_data['Trading_Date'].dt.date.copy()

                return self.stock_data
            
            except KeyError as e:
                raise KeyError(f"Stocks for {kwargs['start']} were unable to return data.  Key Error at {str(e)}")
            except Exception as e:
                raise e

    def _create_stocks_df(self, list_of_stocks, data):

        try:
            stocks_df = pd.DataFrame()
            list_of_data = []
            for stock in list_of_stocks:
                try:
                    if stock == 'AAPL':
                            True
                    stock_dict = {'Trading_Date':data.index,
                                'Open_Price':data[('Open', stock)].values,
                                'High_Price':data[('High', stock)].values,
                                'Low_Price':data[('High', stock)].values,
                                'Close_Price':data[('Close', stock)].values,
                                'Volume':data[('Volume',stock)].values
                                }
                    stock_df = pd.DataFrame(stock_dict)
                    if stock_df.empty:
                          print(f"{stock} doesn't have any data, we will not upload data for the stock")
                          continue  
                    #remove dates that have a close price without a value
                    stock_df = stock_df.loc[~stock_df['Close_Price'].isna()].copy()
                    stock_df['Ticker'] = stock  
                    list_of_data.append(stock_df)    
                except Exception as e:
                    print(e)
                    continue
                stocks_df = pd.concat(list_of_data)
            return stocks_df
        except Exception as e:
            raise e
