import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import boto3
from smart_open import open

st.title('Blue Physics Analysis')

s3 = boto3.client('s3')

response = s3.list_objects_v2(Bucket='indradas')

indrafiles = [file['Key'] for file in response.get('Contents', [])][1:]

dates = []
notes = []

for filename in indrafiles:
    filenow = open(filename)
    datenow = filenow.readline()[11:]
    dates.append(datenow)
    notenow = filenow.readline()[7:]
    notes.append(notenow)
    filenow.close()

dffiles = pd.DataFrame({'file':indrafiles, 'date':dates, 'note':notes})
i_list = dffiles.index[dffiles.date.str.contains('000')].tolist()
dffiles.drop(i_list, inplace = True)
dffiles['date'] = pd.to_datetime(dffiles.date)
dffiles.sort_values(by='date', inplace = True)
dffiles.reset_index(inplace = True, drop = True)
st.write('List of Files')
st.dataframe(dffiles)

filenow = st.selectbox('Select File to Analyze', dffiles.file)

#Take a quick look at the raw data
dforig = pd.read_csv(filenow, skiprows = 4)
df = dforig.loc[:, ['number', 'time', 'temp', 'ch0', 'ch1']]
#st.dataframe(df)

last_time = df.iloc[-1,1]
zeros = df.loc[(df.time < 1) | (df.time > last_time -1), 'ch0':].mean()
dfzeros = df.loc[:, 'ch0':] - zeros
dfzeros.columns = ['ch0z', 'ch1z']
dfz = pd.concat([df, dfzeros], axis = 1)

dfz0 = dfz.loc[:,['time', 'ch0z']]
dfz0.columns = ['time', 'signal']
dfz0['ch'] = 'sensor'
dfz1 = dfz.loc[:,['time', 'ch1z']]
dfz1.columns = ['time', 'signal']
dfz1['ch'] = 'cerenkov'

dfztp = pd.concat([dfz0, dfz1])
fig1 = px.scatter(dfztp, x='time', y='signal', color = 'ch')
st.plotly_chart(fig1)
