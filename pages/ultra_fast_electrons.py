import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import boto3

st.title('Ultra Fast Analysis Electrons')

s3 = boto3.client('s3')

response = s3.list_objects_v2(Bucket='indradas')

fulllistoffiles = [file['Key'] for file in response.get('Contents', [])][1:]

listoffiles = [file for file in fulllistoffiles if ('ultrafast' in file and 'electrton' in file) or ('conefactor' in file)]

filenow = st.selectbox('Select file to analyze:', listoffiles)

@st.cache_data
def read_dataframe(file):
    path = f's3://indradas/{file}'
    df = pd.read_csv(path, skiprows = 4)
    return df

df = read_dataframe(filenow)

st.dataframe(df)

#Prepare data frame to first plot

last_time = df.iloc[-1,1]
zeros = df.loc[(df.time < 1) | (df.time > last_time - 1), 'ch0':].mean()
dfzeros = df.loc[:, 'ch0':] - zeros
dfzeros.columns = ['ch0z', 'ch1z']
dfz = pd.concat([df, dfzeros], axis = 1)

df0 = dfz.loc[:,['time', 'ch0z']]
df0.columns = ['time', 'voltage']
df0['ch'] = 'sensor'
df1 = dfz.loc[:, ['time', 'ch1z']]
df1.columns = ['time', 'voltage']
df1['ch'] = 'cerenkov'
dftp = pd.concat([df0, df1])

@st.cache_data
def plotfigch(df, x_string = 'time', y_string = 'voltage'):
    fig = px.scatter(df, x= x_string, y = y_string, color='ch')
    return fig

@st.cache_data
def plotfig(df, x_string = 'time', y_string = 'voltage'):
    fig = px.scatter(df, x= x_string, y = y_string)
    return fig

fig1 = plotfigch(dftp)

st.plotly_chart(fig1)

t0 = st.number_input('time before beam on', min_value=0.0, max_value=df.time.round(1).max())
t1 = st.number_input('time after beam off', min_value=0.0, max_value=df.time.round(1).max())
t2 = st.number_input('time begining of PDD', min_value=0.0, max_value=df.time.round(1).max())
t3 = st.number_input('time end of PDD', min_value=0.0, max_value=df.time.round(1).max())
depth = st.number_input('PDD depth (mm)', min_value=0, value = 130)
t4 = st.number_input('time begining of profile', min_value=0.0, max_value=df.time.round(1).max())
t5 = st.number_input('time end  of profile', min_value=0.0, max_value=df.time.round(1).max())
pulsesthreshold = st.slider('Chose threshold for pulses', min_value = 1, max_value = 20, value = 5)
ACR = st.number_input('ACR', value = 0.851)

#calculate zeros
nzeros = df.loc[(df.time < t0) | (df.time > t1), 'ch0':].mean()
dfnzeros = df.loc[:, ['ch0', 'ch1']] - nzeros
dfnzeros.columns = ['ch0z', 'ch1z']
dfz = pd.concat([df, dfnzeros], axis=1)
#prepare to plot zeros
df0z = dfz.loc[:, ['time', 'ch0z']]
df0z.columns = ['time', 'voltage']
df0z['ch'] = 'sensor'
df1z = dfz.loc[:, ['time', 'ch1z']]
df1z.columns = ['time', 'voltage']
df1z['ch'] = 'cerenkov'
dftpz = pd.concat([df0z, df1z])
#plot zeros
fig2 = plotfigch(dftpz)
fig2.add_vline(x=t0, line_dash = 'dash', line_color = 'green', opacity = 0.5)
fig2.add_vline(x=t1, line_dash = 'dash', line_color = 'red', opacity = 0.5)
fig2.add_vrect(x0 = t2, x1 = t3, line_width = 0, fillcolor = 'red', opacity = 0.2)
fig2.add_vrect(x0 = t4, x1 = t5, line_width = 0, fillcolor = 'green', opacity = 0.2)
st.plotly_chart(fig2)
#find pulses
maxzeros = dfz.loc[(dfz.time < t0) | (dfz.time > t1), 'ch0z'].max()
dfz['pulse'] = (dfz.ch0z > maxzeros * (1 + pulsesthreshold / 100))
#find coincide pulses
dfz['pulseafter'] = dfz.pulse.shift(-1)
dfz['pulsecoincide'] = dfz.pulse + dfz.pulseafter == 2
dfz['singlepulse'] = dfz.pulse
dfz['pulsecoincideafter'] = dfz.pulsecoincide.shift()
dfz.dropna(inplace = True)
dfz.loc[dfz.pulsecoincideafter, 'singlepulse'] = False
numberofpulses = dfz[(dfz.time > t2) & (dfz.time < t3)].pulse.sum()
numberofpulsescoincide = dfz[(dfz.time > t2) & (dfz.time < t3)].pulsecoincide.sum()
numberofsinglepulses = dfz[(dfz.time > t2) & (dfz.time < t3)].singlepulse.sum()
st.write(f'Number of pulses: {numberofpulses}')
st.write(f'Number of pulses coinciding: {numberofpulsescoincide}')
st.write(f'Number of single pulses: {numberofsinglepulses}')
#find complete dose of pulse and pulseafter
dfz['chargesensor'] = dfz.ch0z * 0.03
dfz['chargecerenkov'] = dfz.ch1z * 0.03
dfz['dose'] = dfz.chargesensor - dfz.chargecerenkov * ACR
dfz['doseafter'] = 0
dfz.loc[dfz.pulsecoincideafter, 'doseafter'] = dfz.dose
dfz['completedose'] = dfz.dose + dfz.doseafter.shift(-1)
dfz.loc[dfz.pulsecoincideafter, 'completedose'] = 0
dfztoplot = dfz[(dfz.time > t2) & (dfz.time < t3)]
fig3 = plotfig(dfztoplot,  x_string = 'time', y_string = 'completedose')
st.plotly_chart(fig3)
#calculate PDD
dfzpdd = dfz[(dfz.time > t2) & (dfz.time < t3)]
manualspeed = st.checkbox('Manual Speed')
if manualspeed:
    realvel = st.number_input('Set the speed manually (mm/s)', value = 7.65)
else:
    realvel = depth / (t3 - t2)
st.write('Speed measured: %.2f mm/s' %realvel)
dfzpdd['disttraveled'] = dfzpdd.time.diff() * realvel
dfzpdd['pos1'] = dfzpdd.disttraveled.cumsum()
dfzpdd['pos'] = depth - dfzpdd.pos1 - 10
fig4 = plotfig(dfzpdd, x_string ='pos', y_string ='completedose')
st.plotly_chart(fig4)
#Soft PDD
dfzallpdd = dfz[(dfz.time > t2) & (dfz.time < t3)]
numberofsamples = len(dfzallpdd)
samplespermm = numberofsamples / depth
st.write('Number of samples per mm: %s' %int(samplespermm))
numberofpulses = dfzpdd.singlepulse.sum()
pulsespermm = numberofpulses / depth
st.write('Number of pulses per mm: %s' %int(pulsespermm))
softvalue = st.slider('Rolling average  value', min_value = 0, value = 200, max_value = 1000)
dfzpdd['softdose'] = dfzpdd.completedose.rolling(softvalue, center = True).sum()
dfzpdd['dosepercent'] = dfzpdd.softdose / dfzpdd.softdose.max() * 100
fig5 = px.line(dfzpdd, x='pos', y='dosepercent')
st.plotly_chart(fig5)
#Calculate profile
dfzprofile = dfz.loc[(dfz.time > t4) & (dfz.time < t5)]
fig6 = plotfig(dfzprofile, x_string = 'time', y_string = 'completedose')
st.plotly_chart(fig6)
profilemax = st.slider('soft value to calculate maximum', min_value=0.9, max_value =1.0, value=1.0)
profilespeed = st.number_input('estimated motor speed', min_value = 8.00, max_value = 15.00, value = 9.26)
dfzprofile['disttraveled'] = dfzprofile.time.diff() * profilespeed
dfzprofile['pos1'] = dfzprofile.disttraveled.cumsum()
centerprofile = dfzprofile.loc[dfzprofile.completedose >= dfzprofile.completedose.max() * profilemax, 'pos1'].median()
st.write('center of profile: %.2f' %centerprofile)
dfzprofile['pos'] = dfzprofile.pos1 - centerprofile
fig7 = plotfig(dfzprofile, x_string = 'pos', y_string = 'completedose')
st.plotly_chart(fig7)
profilemindose1 = st.number_input('Profile dose threshold (0.00xx)', value = 60)
profilemindose = profilemindose1 / 10000
profilesoft = st.slider('Soft value for profile', min_value =0, max_value =100, value = 50)
dfzgp = dfzprofile[dfzprofile.completedose > profilemindose]
dfzgp['dosesoft'] = dfzgp.completedose.rolling(profilesoft, center = True).mean()
dfzgp['dosepercent'] = dfzgp.dosesoft / dfzgp.dosesoft.max() * 100
fig9 = plotfig(dfzgp, x_string = 'pos', y_string = 'dosepercent')
st.plotly_chart(fig9)
