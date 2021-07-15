import pylum.curves
import pickle
import dash
from dash.dependencies import Input, Output, State
import dash_core_components as dcc
import dash_html_components as html
import base64
import pickle
from plotly import express as px
import io

app=dash.Dash(__name__)

app.layout=html.Div([
    dcc.Upload(
        id='upload-data',
        children=html.Div([
            'Drag and drop or ',
            html.A('Select Files')
        ])
    ),
    dcc.Graph(id='disp-graph')
])

@app.callback(Output('disp-graph','figure'),
              Input('upload-data','contents'),prevent_initial_call=True)
def show_graph(data):
    data_bytes=base64.b64decode(data.split(',')[1]) #data comes in as content_type,content
    curves=pickle.loads(data_bytes)
    all_keys=curves.keys()
    this_curve=curves[all_keys[0]]
    fig=px.scatter(this_curve.get_approach(),x=this_curve.cols['z'],y=this_curve.cols['f'])
    fig.update_layout(hovermode=False)
    return fig

if __name__=='__main__':
    app.run_server(debug=True)
