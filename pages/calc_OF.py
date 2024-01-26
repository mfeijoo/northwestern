import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import boto3
#from glob import glob

st.title('Calculate OF')

s3 = boto3.client('s3')

response = s3.list_objects_v2(Bucket='indradas')

filenames = [file['Key'] for file in response.get('Contents', [])][1:]

#filenames = glob('Indra*.csv')

listnoultrafast = [i for i in filenames if 'ultrafast' not in i]

filenames = st.multiselect('Select files to calculate OF', listnoultrafast)

@st.cache_data
def read_dataframes(files):
    dfs = []
    for file in files:
        path = f's3://indradas/{file}'
        df = pd.read_csv(path, skiprows = 4)
        #df = pd.read_csv(file, skiprows = 4)
        dfs.append(df)
    return dfs

dfs = read_dataframes(filenames)

cutoff = st.selectbox('cut off', [0.5, 10, 20, 40, 100, 150], index = 3)

ACR = st.number_input('ACR value', value = 0.83, format = '%.2f')

dfis = []
for df in dfs:
    last_time = df.iloc[-1,1]
    zeros = df.loc[(df.time < 1) | (df.time > last_time - 1), 'ch0':].mean()
    dfchz = df.loc[:, 'ch0':] - zeros
    dfchz.columns = ['ch0z', 'ch1z']
    dfz = pd.concat([df, dfchz], axis = 1)

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

    for (n, (s, f)) in enumerate(zip(sts, fts)):
        dfz.loc[(dfz.time > s) & (dfz.time < f), 'shot'] = n


    dfi = dfz.groupby('shot').agg({'sensorcharge':np.sum,
                                'cerenkovcharge':np.sum,
                                'dose':np.sum,
                                'singlepulse':np.sum})
    dfis.append(dfi)

dfit = pd.concat(dfis)
st.dataframe(dfit)

fsizes = st.text_input('select field sizes (cm) separated by commas',
        value = '0.5,0.5,0.5,10,10,10,5,5,5,4,4,4,3,3,3,2,2,2,1.5,1.5,1.5,1.2,1.2,1.2,1,1,1,0.8,0.8,0.8,10,10,10')
listsizes = fsizes.split(',')
sizesint = [float(i) for i in listsizes]
if len(sizesint) != len(dfit):
    st.error('Wrong number of field sizes')
dfit['field'] = sizesint
dfit['OF'] = dfit.dose / dfit.loc[dfit.field == 10, 'dose'].mean()
of = dfit.groupby('field').mean()
of['error'] = dfit.groupby('field').std()['OF']
of.reset_index(inplace = True)
fig1 = go.Figure()
go1 = go.Scatter(
        x= of['field'],
        y = of['OF'],
        name = 'Blue Physics',
        mode = 'markers',
        error_y = dict(type = 'data',
                        array = of['error'],
                        visible = True)
        )
fig1.add_traces(go1)
fig1.update_xaxes (title_text='Field Size (cm)')
fig1.update_yaxes (title_text = 'OF')
fig1.update_layout(title = 'OF')
st.dataframe(of.loc[:,['field', 'dose',  'OF', 'error']])
sensor2 = st.text_input('Name of sensor2', value='MC')
if sensor2 != 'None':
    s2ofs = st.text_input('sensor2 OFs (separated by commas)',
            value = '0.405,0.647,0.718,0.76,0.798,0.837,0.87,0.898,0.921,1')
    listsensor2 = s2ofs.split(',')
    listsensor2float = [float(i) for i in listsensor2]
    sensor2fields = st.text_input('sensor2 field sizes (separated by commas)',
            value = '0.5, 0.8,1,1.2,1.5,2,3,4,5,10')
    listofsensor2fields = sensor2fields.split(',')
    listofsensor2fieldsfloat = [float(i) for i in listofsensor2fields]
    fig1.add_traces(
            go.Scatter(
                x = listofsensor2fieldsfloat,
                y = listsensor2float, 
                mode = 'lines+markers',
                marker = dict(color = 'red', opacity = 0.5),
                line = dict(color = 'rgba(255, 0, 0, 0.5)'),
                name = sensor2                
                )
            )

sensor3 = st.text_input('Name of sensor3', value='microSilicon')
if sensor3 != 'None':
    s3ofs = st.text_input('sensor3 OFs (separated by commas)',
            value = '1,0.871, 0.834, 0.711, 0.46')
    listsensor3 = s3ofs.split(',')
    listsensor3float = [float(i) for i in listsensor3]
    sensor3fields = st.text_input('sensor3 field sizes (separated by commas)',
            value = '10,3,2,1,0.5')
    listofsensor3fields = sensor3fields.split(',')
    listofsensor3fieldsfloat = [float(i) for i in listofsensor3fields]
    fig1.add_traces(
            go.Scatter(
                x = listofsensor3fieldsfloat,
                y = listsensor3float, 
                mode = 'markers',
                marker = dict(color = 'green', opacity = 0.5),
                name = sensor3                
                )
            )
st.plotly_chart(fig1)
