import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import boto3

st.title('Calculate integrals of shots')

s3 = boto3.client('s3')

response = s3.list_objects_v2(Bucket='indradas')

indrafiles = [file['Key'] for file in response.get('Contents', [])][1:]

listnoultrafast = [i for i in indrafiles if 'ultrafast' not in i]

filename = st.selectbox('Select file to calculate integrals', listnoultrafast)

@st.cache_data
def read_dataframe(file):
    path = f's3://indradas/{file}'
    df = pd.read_csv(path, skiprows = 4)
    return df

df = read_dataframe(filename)

cutoff = st.selectbox('cut off', [0.5, 10, 20, 40, 100, 150], index = 3)

last_time = df.iloc[-1,1]
zeros = df.loc[(df.time < 1) | (df.time > last_time - 1), 'ch0':].mean()
dfchz = df.loc[:, 'ch0':] - zeros
dfchz.columns = ['ch0z', 'ch1z']
dfz = pd.concat([df, dfchz], axis = 1)

ACR = st.number_input('ACR value', value = 0.851)
dfz['sensorcharge'] = dfz.ch0z * 0.03
dfz['cerenkovcharge'] = dfz.ch1z * 0.03
dfz['dose'] = dfz.sensorcharge - dfz.cerenkovcharge * ACR

dfz['chunk'] = dfz.number // (300000/700)
group = dfz.groupby('chunk')
dfg = group.agg({'time':np.median,
                'ch0z':np.sum,
                'ch1z':np.sum})
dfg['time_min'] = group['time'].min()
dfg['time_max'] = group['time'].max()
dfg['ch0diff'] = dfg.ch0z.diff()
starttimes = dfg.loc[dfg.ch0diff > cutoff, 'time_min']
finishtimes = dfg.loc[dfg.ch0diff < -cutoff, 'time_max']
stss = [starttimes.iloc[0]] + list(starttimes[starttimes.diff()>2])
sts = [t - 0.04 for t in stss]
ftss = [finishtimes.iloc[0]] + list(finishtimes[finishtimes.diff()>2])
fts = [t + 0.04 for t in ftss]

#Find pulses
maxvaluech = dfz.loc[(dfz.time < sts[0] - 1) | (dfz.time > fts[-1] + 1), 'ch0z'].max()
dfz['pulse'] = dfz.ch0z > maxvaluech * 1.05
dfz.loc[dfz.pulse, 'pulsenum'] = 1
dfz.fillna({'pulsenum':0}, inplace = True)
dfz['pulsecoincide'] = dfz.loc[dfz.pulse, 'number'].diff() == 1
dfz.fillna({'pulsecoincide':False}, inplace = True)
dfz['singlepulse'] = dfz.pulse & ~dfz.pulsecoincide
dfz['pulsetoplot'] = dfz.singlepulse * 0.02 

dfz0 = dfz.loc[:, ['time', 'sensorcharge']]
dfz0.columns = ['time', 'signal']
dfz0['ch'] = 'sensor'
dfz1 = dfz.loc[:, ['time', 'cerenkovcharge']]
dfz1.columns = ['time', 'signal']
dfz1['ch'] = 'cerenkov'
dfz2 = dfz.loc[:, ['time', 'pulsetoplot']]
dfz2.columns = ['time', 'signal']
dfz2['ch'] = 'pulse'
dfztp = pd.concat([dfz0, dfz1, dfz2])

@st.cache_data
def plotgraph(df):
    fig = px.scatter(df, x = 'time', y = 'signal', color = 'ch')
    return fig

fig0 = plotgraph(dfztp)

for (n, (s, f)) in enumerate(zip(sts, fts)):
    fig0.add_vline(x=s, line_dash = 'dash', line_color = 'green', opacity = 0.5)
    fig0.add_vline(x=f, line_dash = 'dash', line_color = 'red', opacity = 0.5)
    dfz.loc[(dfz.time > s) & (dfz.time < f), 'shot'] = n

st.plotly_chart(fig0)

dfi = dfz.groupby('shot').agg({'sensorcharge':np.sum,
                                'cerenkovcharge':np.sum,
                                'dose':np.sum,
                                'singlepulse':np.sum})

st.dataframe(dfi)

