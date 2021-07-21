import pickle
import pandas as pd
from plotly import graph_objs as go
from plotly import offline as py
import numpy as np

dark_colors=['rgb(31, 119, 180)', 'rgb(255, 127, 14)',
             'rgb(44, 160, 44)', 'rgb(214, 39, 40)',
             'rgb(148, 103, 189)', 'rgb(140, 86, 75)',
             'rgb(227, 119, 194)', 'rgb(127, 127, 127)',
             'rgb(188, 189, 34)', 'rgb(23, 190, 207)']

light_colors=['rgba(31, 119, 180, .2)', 'rgba(255, 127, 14, .2)',
              'rgba(44, 160, 44, .2)', 'rgba(214, 39, 40, .2)',
              'rgba(148, 103, 189, .2)', 'rgba(140, 86, 75, .2)',
              'rgba(227, 119, 194, .2)', 'rgba(127, 127, 127, .2)',
              'rgba(188, 189, 34, .2)', 'rgba(23, 190, 207, .2)']

class Curve:
    contact_index=None
    approach_range=[]
    dwell_range=[]
    k=None
    invOLS=None
    data=None
    parameters=None
    cols=None

    def __init__(self,filename,data,parameters,z_col,t_col,f_col,invOLS,k,dwell_range):
        self.dwell_range=dwell_range
        self.k=k
        self.invOLS=invOLS
        self.data=data
        self.parameters=parameters
        self.cols={'z':z_col,'t':t_col,'f':f_col}
        self.filename=filename

    def get_approach(self):
        return self.data.loc[0:self.dwell_range[0],:]

    def get_dwell(self):
        return self.data.loc[self.dwell_range[0]:self.dwell_range[1],:]

    def get_retract(self):
        return self.data.loc[self.dwell_range[1]:,:]

class CurveSet:
    ident_labels=None
    curve_dict=None

    def __init__(self,ident_labels,curve_dict):
        self.ident_labels=ident_labels
        self.curve_dict=curve_dict

    def __iter__(self):
        return self.curve_dict.__iter__()
    
    def pickle(self,filename):
        with open(filename,'wb') as f:
            pickle.dump(self,f)

    def keys(self):
        return list(self.curve_dict.keys())

    def __getitem__(self,index):
        return self.curve_dict[index]

    def collate_curves(self):
        all_curves=[]
        for ident in self.keys():
            this_curve=self[ident].data.copy()
            for label,value in zip(self.ident_labels,ident):
                this_curve.loc[:,label]=value
            all_curves.append(this_curve)
        return pd.concat(all_curves,ignore_index=True)
    
    #def normalize_curves(curves,idents,t_col='t',z_col='zSensr',f_col='force'):
    def normalize_curves(self):
        curves=self.collate_curves()
        idents=list(self.ident_labels)
        cols=self[self.keys()[0]].cols
        t_col=cols['t']
        z_col=cols['z']
        f_col=cols['f']
        desired_cols=[*idents,t_col,z_col,f_col]
        curves=curves.loc[:,desired_cols]

        maxf=curves.loc[:,[*idents,f_col]].groupby(idents).agg(np.max).reset_index()
        maxf_cols=list(maxf.columns)
        for i in range(len(maxf_cols)):
            if maxf_cols[i]==f_col:
                maxf_cols[i]='max_f'

        maxf.columns=maxf_cols

        curves=pd.merge(curves,maxf)
        norm_vals=curves.query(f'{f_col}==max_f')
        norm_vals=norm_vals.loc[:,[*idents,t_col,z_col]]
        norm_cols=list(norm_vals.columns)
        for j in range(len(norm_cols)):
            if norm_cols[j]==t_col:
                norm_cols[j]='t0'
            elif norm_cols[j]==z_col:
                norm_cols[j]='z0'

        norm_vals.columns=norm_cols

        curves=pd.merge(curves,norm_vals)
        curves.loc[:,'t_norm']=curves.loc[:,t_col]-curves.loc[:,'t0']
        curves.loc[:,'z_norm']=curves.loc[:,z_col]-curves.loc[:,'z0']
        curves.loc[:,'f_norm']=curves.loc[:,f_col]-curves.loc[:,'max_f']

        curves=curves.loc[:,[*idents,'t_norm','z_norm','f_norm']]

        return curves




    #def plot_traj(data,group,filename='characteristic_trajectories.html',round_dec=4):
    def plot_traj(self,group,filename='characteristic_trajectories.html',round_dec=4):
        data=self.normalize_curves()
        time_col='t_norm'
        f_col='f_norm'
        data.loc[:,group]=[str(a) for a in data.loc[:,group]]
        data=data.loc[:,[group,time_col,f_col]]
        data.loc[:,time_col]=[np.round(a,round_dec) for a in data.loc[:,time_col]]
        upper=data.groupby([group,time_col]).agg(lambda x: np.quantile(x,.75)).reset_index()
        median=data.groupby([group,time_col]).agg(lambda x: np.quantile(x,.5)).reset_index()
        lower=data.groupby([group,time_col]).agg(lambda x: np.quantile(x,.25)).reset_index()

        upper.loc[:,'metric']='upper'
        median.loc[:,'metric']='median'
        lower.loc[:,'metric']='lower'



        all_metrics=pd.concat([upper,median,lower],ignore_index=True)

        #all_metrics.loc[:,'physical_line']=[str(a)+'_'+str(b) for a,b in zip(all_metrics.loc[:,group],all_metrics.loc[:,'metric'])]
        traces=[]
        all_groups=list(set(all_metrics.loc[:,group]))
        num_reps=np.ceil(len(all_groups)/len(dark_colors))
        for g,dark_c,light_c in zip(all_groups,int(num_reps)*dark_colors,int(num_reps)*light_colors):
            this_group=all_metrics.loc[all_metrics.loc[:,group]==g,:]
            this_median=this_group.loc[this_group.loc[:,'metric']=='median']
            this_upper=this_group.loc[this_group.loc[:,'metric']=='upper']
            this_lower=this_group.loc[this_group.loc[:,'metric']=='lower']
            main_trace=go.Scatter(x=this_median[time_col],
                                  y=this_median[f_col],
                                  line=dict(color=dark_c),
                                  mode='lines',
                                  name=g+' median')
            error_trace=go.Scatter(x=list(this_upper[time_col])+list(this_lower[time_col])[::-1],
                                   y=list(this_upper[f_col])+list(this_lower[f_col])[::-1],
                                   fill='toself',
                                   fillcolor=light_c,
                                   line=dict(color='rgba(255,255,255,0)'),
                                   hoverinfo="skip",
                                   name=g+' error')
            traces.extend([main_trace,error_trace])

        fig=go.Figure(traces)

        py.plot(fig,filename=filename)
        return all_metrics
