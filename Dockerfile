FROM python:3.11-slim-bullseye
WORKDIR /usr/local/app


# Install the application dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt


#copy the project to the container
COPY ./stock_data  ./stock_data
COPY main.py ./

# Setup an app user so the container doesn't run as the root user
RUN useradd app
USER app


CMD ["python", "main.py"] 