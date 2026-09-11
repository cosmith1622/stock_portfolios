from stock_data import portfolio_data
from stock_data import analysis
from stock_data import portfolio
from stock_data import stock_data
from stock_data import s3_connector
import pandas as pd
import numpy as np
from curl_cffi import requests
import io
import sys
import os
from datetime import timedelta, date


def stocks_to_buy():

    today = date.today()
    """
    
        we are going to get two years from today
        so we have compute all the metrics
    
    """
    two_years_ago = today + timedelta(days=-730)
    ana = analysis()
    df = ana.get_stock_data(start_date=two_years_ago)
    s3 = s3_connector()
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    s3.put_object(csv_buffer,'stock-bucket-01','stocks_to_trade')
    df = ana.data_analysis(df,252)

    pf = portfolio(df,150,5000,20, False, False)
    performance_df = pf.update_portfolio()

    csv_buffer = io.StringIO()
    stock_to_buy_df = pd.DataFrame(pf.stocks_to_purchase)
    stock_to_buy_df.to_csv(csv_buffer, index=False)
    file_name = date.today()
    file_name = f"stocks_to_purchase_{file_name.strftime('%Y-%m-%d')}.csv"
    s3.put_object(csv_buffer,'stock-bucket-01',file_name)
    print('cole')

    """
    performance_df.to_csv('performance.csv', index=False,mode='w')
    s3.upload_file('./performance.csv', 'stock-bucket-01', 'performance')
    """


def get_new_data():

    """
        Step 1 Get the latest stock date in the database.
        If that stock exist in Step 2, we will get the 
        latest information for the stock.

    """
    print(os.environ)
    pdata = portfolio_data()
    data = pdata.get_latest_stock_data('stock-bucket-01')

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
    


    #Push the new stock data into the redshift db


    pdata.insert_price_data('stock-bucket-01')


if __name__ == "__main__":

    
    if os.environ['start_up_args'] == '1':
        get_new_data()
    elif os.environ['start_up_args'] =='2':
        stocks_to_buy()

