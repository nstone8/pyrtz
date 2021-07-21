import dash
from dash.dependencies import Input, Output, State
import dash_core_components as dcc
import dash_html_components as html
from plotly import express as px
from plotly import graph_objs as go
import random
import sys
from pylum import asylum as asy
import json

all_curve_fig=None
all_curve_data=None
all_curve_idents=None

app=dash.Dash(__name__)

app.layout=html.Div([
    'Curve',
    html.Div(id='curve-count'),
    html.Button('<',id='back-button',n_clicks=0),
    html.Button('>',id='forward-button',n_clicks=0),
    dcc.Graph(id='disp-graph'),
    html.Br(),
    dcc.Store(id='selected-indices'),
    'Selected Point Index',
    html.Div(id='this-selected-point')
    
])

def key_index_from_str(curve_count):
    return int(curve_count.split('/')[0])-1

def key_index_to_str(key_index):
    return f'{key_index+1}/{len(all_curve_idents)}'

@app.callback(Output('curve-count','children'),
              Input('back-button','n_clicks'),
              Input('forward-button','n_clicks'))
def update_curve_number(back_clicks,forward_clicks):
    new_index=forward_clicks-back_clicks
    if new_index<0:
        new_index=0
    return key_index_to_str(new_index)

@app.callback(Output('disp-graph','figure'),
              Input('curve-count','children'),
              Input('selected-indices','data'))
def show_graph(curve_count,selected_indices):
    this_key_index=key_index_from_str(curve_count)
    this_key=all_curve_idents[this_key_index]
    this_curve_data=all_curve_data[this_key]
    fig=go.Figure(all_curve_fig[this_key])
    if selected_indices:
        selected_index_dict=json.loads(selected_indices)
        selected_index=selected_index_dict[repr(this_key)]
    else:
        selected_index=0
    fig.add_vline(x=this_curve_data.loc[selected_index,'z'])
    return fig

@app.callback(Output('selected-indices','data'),
              Input('disp-graph','clickData'),
              State('curve-count','children'),
              State('selected-indices','data'),prevent_initial_call=True)
def handle_click(clicked,curve_count,data):
    this_selection=[a['pointNumber'] for a in clicked['points']]
    key_index=key_index_from_str(curve_count)
    new_selected_index=min(this_selection)
    if data:
        selected_dict=json.loads(data)
    else:
        selected_dict={}
        for key in all_curve_idents:
            selected_dict[repr(key)]=0
    selected_dict[repr(all_curve_idents[key_index])]=new_selected_index
    return json.dumps(selected_dict)

@app.callback(Output('this-selected-point','children'),
              Input('selected-indices','data'),
              Input('curve-count','children'))
def update_selected_point_index(selected_dict_json,curve_count):
    if not selected_dict_json:
        return 0
    key_index=key_index_from_str(curve_count)
    selected_dict=json.loads(selected_dict_json)
    return selected_dict[repr(all_curve_idents[key_index])]

if __name__=='__main__':
    if len(sys.argv)<3:
        raise Exception('annocp should be invoked using a statement like: python -m pylum.annocp cuve_directory ident_label1 ident_label2...')
    curve_dir=sys.argv[1]
    print(f'Loading curves from directory: {curve_dir}')
    ident_labels=sys.argv[2:]
    print(f'ident labels are: {str(ident_labels)}')
    curve_set=asy.load_curveset_ibw(curve_dir,ident_labels)
    curve_figs={}
    curve_data={}
    curves_processed=1
    num_curves=len(curve_set.keys())
    for ident in curve_set:
        print(f'\rMaking figure object for curve {curves_processed} of {num_curves}',end='')
        this_curve=curve_set[ident]
        this_curve_data=this_curve.get_approach().rename(columns=this_curve.cols)
        fig=px.scatter(this_curve.get_approach(),x='z',y='f')
        #hovermode=False
        fig.update_layout(clickmode='event+select')
        fig.update_xaxes(autorange='reversed')
        curve_figs[ident]=fig
        curve_data[ident]=this_curve_data
        curves_processed+=1
    print('')
    curve_idents=curve_set.keys()
    my_random=random.Random(curve_dir) #make shuffle deterministic so if dash uses multiple workers they will all have the same dataset order
    my_random.shuffle(curve_idents)
    #global all_curve_fig,all_curve_idents,all_curve_data
    all_curve_fig=curve_figs
    all_curve_idents=curve_idents
    all_curve_data=curve_data
    app.run_server(debug=True)
