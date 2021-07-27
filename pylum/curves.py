import pickle
import pandas as pd
from plotly import graph_objs as go
from plotly import offline as py
import numpy as np
import json
import ast
import scipy.optimize
from plotly import express as px
import io
import PyPDF2 as pdf

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
    stiff_fit=None
    biexponential_fit=None
    
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

    def set_contact_index(self,cp):
        self.contact_index=cp

    def fit_stiffness(self,probe_diameter,fit_range=[0,1]):
        if self.contact_index==None:
            raise Exception('Contact index has not been set, stiffness fits cannot continue')
        
        r=probe_diameter/2
        #Get only contact region and adjust force and indentation so values at contact are 0
        indent_raw=self.get_approach().loc[self.contact_index:,self.cols['z']].to_numpy()
        force_raw=self.get_approach().loc[self.contact_index:,self.cols['f']].to_numpy()
        indent_norm=indent_raw-indent_raw[0]
        force_norm=force_raw-force_raw[0]
        def get_force(indentation,e_star):
            return (4/3)*e_star*(r**0.5)*(indentation**1.5)

        #Figure out data subset for fitting
        fmin=force_norm[-1]*fit_range[0]
        fmax=force_norm[-1]*fit_range[1]

        imin=0
        imax=0
        for i in list(range(len(force_norm)))[::-1]:
            if force_norm[i]>=fmin:
                imin=i
            if force_norm[i]>=fmax:
                imax=i

        indent_norm_fit=indent_norm[imin:imax]
        force_norm_fit=force_norm[imin:imax]

        #run fit
        popt,pcov=scipy.optimize.curve_fit(get_force,indent_norm_fit,force_norm_fit)

        estar_fit=popt[0]
        fit_curve=pd.DataFrame(dict(z=indent_norm_fit+indent_raw[0],f=get_force(indent_norm_fit,estar_fit)+force_raw[0]))
        self.stiff_fit=dict(curve=fit_curve,estar=estar_fit)

    def get_stiffness_fit_figure(self):
        if not self.stiff_fit:
            raise Exception('No stiffness fit has yet been performed. Run fit_stiffness method')

        measured_curve=self.get_approach().rename(columns=self.cols)
        measured_curve.loc[:,'curve']='measured'
        fit_curve=self.stiff_fit['curve'].copy()
        fit_curve.loc[:,'curve']='fit'
        all_curves=pd.concat([measured_curve,fit_curve],ignore_index=True)
        fig=px.scatter(all_curves,x='z',y='f',color='curve')
        fig.update_xaxes(title={'text':'Z Position (m)'})
        fig.update_yaxes(title={'text':'Force (N)'})
        fig.add_vline(x=measured_curve.loc[self.contact_index,'z'])
        return fig

    def fit_biexponential(self):
        fit_data=self.get_dwell().rename(columns=self.cols)
        f_raw=fit_data['f'].to_numpy()
        f0=f_raw[0]
        t_raw=fit_data['t'].to_numpy()
        #adjust time to start at zero when the dwell begins
        t_norm=t_raw-t_raw[0]

        #make some good initial guesses
        c_guess=f_raw[-1]
        #force value corresponding to ~63% relaxation
        e_threshold=f0-0.63*(f0-c_guess)
        #corresponding time
        e_time=fit_data.loc[fit_data.loc[:,'f']<e_threshold,'t'].to_numpy()[0]
        tau1_guess=1/e_time
        tau2_guess=0.1*tau1_guess
        a_guess=0.9 #arbitrary, took from rasylum, seems to work

        def calc_force(t,tau1,tau2,A,C):
            return (f0-C)*(A*np.exp(-1*t*tau1)+(1-A)*np.exp(-1*t*tau2))+C

        bounds=([0,0,0,-np.inf],[np.inf,np.inf,1,np.inf])
        p0=[tau1_guess,tau2_guess,a_guess,c_guess]

        popt,pconv=scipy.optimize.curve_fit(calc_force,t_norm,f_raw,bounds=bounds,p0=p0)
        biexponential_fit=dict(tau1=popt[0],tau2=popt[1],A=popt[2],C=popt[3])

        fit_curve=pd.DataFrame(dict(t=fit_data['t'],f=calc_force(t_norm,biexponential_fit['tau1'],biexponential_fit['tau2'],biexponential_fit['A'],biexponential_fit['C'])))

        biexponential_fit['curve']=fit_curve
        biexponential_fit['tau_fast']=max(biexponential_fit['tau1'],biexponential_fit['tau2'])
        biexponential_fit['tau_slow']=min(biexponential_fit['tau1'],biexponential_fit['tau2'])
        self.biexponential_fit=biexponential_fit

    def get_biexponential_fit_figure(self):
        if not self.biexponential_fit:
            raise Exception('No biexponential fit has yet been performed. Run fit_biexponential method')

        measured_curve=self.get_dwell().rename(columns=self.cols)
        measured_curve.loc[:,'curve']='measured'

        fit_curve=self.biexponential_fit['curve'].copy()
        fit_curve.loc[:,'curve']='fit'

        all_curves=pd.concat([measured_curve,fit_curve],ignore_index=True)
        fig=px.scatter(all_curves,x='t',y='f',color='curve')
        fig.update_xaxes(title={'text':'Time (s)'})
        fig.update_yaxes(title={'text':'Force (N)'})
        return fig
    
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

    def remove_curve(self,key):
        del self.curve_dict[key]

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

    def update_cp_annotations(self,cp_dict):
        for key in cp_dict:
            self[key].set_contact_index(cp_dict[key])

    def update_cp_annotations_from_file(self,cp_file):
        with open(cp_file,'rt') as cf:
            anno_str_dict=json.load(cf)

        anno_tuple_dict={}
        for key in anno_str_dict:
            tuple_key=ast.literal_eval(key)
            anno_tuple_dict[tuple_key]=anno_str_dict[key]

        self.update_cp_annotations(anno_tuple_dict)

    def fit_all_stiff(self,probe_diameter,fit_range=[0,1]):
        for key in self:
            self[key].fit_stiffness(probe_diameter,fit_range)

    def fit_all_biexponential(self):
        for key in self:
            self[key].fit_biexponential()

    def fit_all(self,probe_diameter,fit_range=[0,1]):
        self.fit_all_stiff(probe_diameter,fit_range)
        self.fit_all_biexponential()

    def get_stiff_results(self):
        entries=[]
        for key in self:
            df_dict={}
            for label,ident in zip(self.ident_labels,key):
                df_dict[label]=[ident]
            df_dict['estar']=[self[key].stiff_fit['estar']]
            entries.append(pd.DataFrame(df_dict))
        return(pd.concat(entries,ignore_index=True))

    def get_biexponential_results(self):
        entries=[]
        for key in self:
            df_dict={}
            for label,ident in zip(self.ident_labels,key):
                df_dict[label]=[ident]
            df_dict['tau1']=[self[key].biexponential_fit['tau1']]
            df_dict['tau2']=[self[key].biexponential_fit['tau2']]
            df_dict['tau_fast']=[self[key].biexponential_fit['tau_fast']]
            df_dict['tau_slow']=[self[key].biexponential_fit['tau_slow']]
            df_dict['A']=[self[key].biexponential_fit['A']]
            df_dict['C']=[self[key].biexponential_fit['C']]
            entries.append(pd.DataFrame(df_dict))
        return(pd.concat(entries,ignore_index=True))
            
    def get_all_results(self):
        stiff_results=self.get_stiff_results()
        biexponential_results=self.get_biexponential_results()
        return pd.merge(stiff_results,biexponential_results)

    def export_stiffness_fit_report(self,filepath):
        merger=pdf.PdfFileMerger()
        for key in self:
            this_curve=self[key]
            if this_curve.stiff_fit==None:
                raise Exception('Stiffness fit has not been performed, please run stiffness fit before attempting to export fit reports')
            title=''
            for label,ident in zip(self.ident_labels,key):
                title=title+f'{label}{ident}'

            title=title+f" estar: {this_curve.stiff_fit['estar']}"
            this_fit_fig=this_curve.get_stiffness_fit_figure()
            this_fit_fig.update_layout(title={'text':title})

            this_fit_fig_pdf=io.BytesIO(this_fit_fig.to_image(format='pdf'))
            merger.append(this_fit_fig_pdf)

        merger.write(filepath)

    def export_biexponential_fit_report(self,filepath):
        merger=pdf.PdfFileMerger()
        for key in self:
            this_curve=self[key]
            if this_curve.biexponential_fit==None:
                raise Exception('Biexponential fit has not been performed, please run biexponential fit before attempting to export fit reports')
            title=''
            for label,ident in zip(self.ident_labels,key):
                title=title+f'{label}{ident}'

            title=title+f" tau_fast: {this_curve.biexponential_fit['tau_fast']}, tau_slow:{this_curve.biexponential_fit['tau_slow']}"
            this_fit_fig=this_curve.get_biexponential_fit_figure()
            this_fit_fig.update_layout(title={'text':title})

            this_fit_fig_pdf=io.BytesIO(this_fit_fig.to_image(format='pdf'))
            merger.append(this_fit_fig_pdf)

        merger.write(filepath)
