from stock_data import portfolio_data
from stock_data import analysis
from stock_data import portfolio
from stock_data import stock_data
import pandas as pd


if __name__ == "__main__":


    test = stock_data()
    #df = test.get_stocks('DCOM', start='2001-01-01', auto_adjust=False, threads=True)
    ana = analysis()
    #ana.get_stock_data()
    df = ana.add_columns(252)
    #df =  df.loc[df['ticker']=='DCOM'].copy()
    #df = df.loc[(df['trading_date']=='2001-01-02') | (df['trading_date']=='2001-01-09')]
    #print(df[['trading_date', 'close_price', 'probability', 'upper_band', 'lower_band']])
    pf = portfolio(df,100,5000,20)
    test1 = pf.update_portfolio()
    #print(test1[['trading_date', 'ticker', 'close_price', 'last_year_price', 'yoy_change']].head())


    """
        Step 1 Get the latest stock date in the database.
        If that stock exist in Step 2, we will get the 
        latest information for the stock.

    """
    pdata = portfolio_data()
    #data =  pdata.get_latest_stock_data('stock-bucket-01')
    data = pd.read_csv('2025-09-27_latest_stock_data_copy.csv')
    data['0'] = '1999-12-31'

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
