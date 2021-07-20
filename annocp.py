import pylum.curves
import pickle
import dash
from dash.dependencies import Input, Output, State
import dash_core_components as dcc
import dash_html_components as html
import base64
import pickle
from plotly import express as px
import random
import json
import pandas as pd

app=dash.Dash(__name__)

app.layout=html.Div([
    dcc.Upload(
        id='upload-data',
        children=html.Div([
            html.A('Select File')
        ])
    ),
    dcc.Store(id='curve-set'),
    'Curve',
    html.Div(id='curve-count'),
    dcc.Store(id='this-approach-frame'),
    dcc.Graph(id='disp-graph'),
    html.Br(),
    'Selected Point Index',
    html.Div(id='selected_point',children=0)
])

@app.callback(Output('curve-count','children'),
              Output('curve-set','data'),
              Input('upload-data','contents'),prevent_initial_call=True)
def cache_all_curves(data):
    data_bytes=base64.b64decode(data.split(',')[1]) #data comes in as content_type,content
    curves=pickle.loads(data_bytes)
    all_keys=curves.keys()
    random.shuffle(all_keys)
    df_json_list=list()
    for k in all_keys:
        print(f'jsonified curve with key {k}')
        df_json_list.append(curves[k].get_approach().rename(columns=curves[k].cols).to_json())

    print('caching curves')
    return '1/'+str(len(all_keys)),json.dumps({'keys':all_keys,'json_dfs':df_json_list})
    
@app.callback(Output('disp-graph','figure'),
              Input('curve-set','data'),
              Input('curve-count','children'),
              Input('selected_point','children'),prevent_initial_call=True)
def show_graph(data,curve_count,selected_index):
    all_curves_json=json.loads(data)
    this_key_index=int(curve_count.split('/')[0])-1
    this_key=all_curves_json['keys'][this_key_index]
    this_frame_json=all_curves_json['json_dfs'][this_key_index]
    this_curve_data=pd.read_json(this_frame_json)
    fig=px.scatter(this_curve_data,x='z',y='f')
    #hovermode=False
    fig.update_layout(clickmode='event+select')
    fig.update_xaxes(autorange='reversed')
    #fig.update_traces(marker=dict(line=dict(width=0)))
    fig.add_vline(x=this_curve_data.loc[selected_index,'z'])
    return fig

@app.callback(Output('selected_point','children'),
              Input('disp-graph','clickData'),prevent_initial_call=True)
def handle_click(clicked):
    print('clicked')
    selected_indices=[a['pointNumber'] for a in clicked['points']]
    return(min(selected_indices))

if __name__=='__main__':
    app.run_server(debug=True)
