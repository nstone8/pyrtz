import igor.binarywave as bw
import numpy as np
import pandas as pd
import pylum.curves
import re
import os

def _get_notes(wave):
    note_raw=wave['wave']['note']
    note_raw=note_raw.replace(b'\xb0',b'deg') #Asylum seems to store the degree sign in a broken way that python can't parse, replace all occurances of this invalid byte sequence with 'deg'
    all_notes=note_raw.split(b'\r')
    note_dict=dict()
    for line in all_notes: 
        split_line=line.split(b':') 
        key=split_line[0] 
        value=b':'.join(split_line[1:]).strip()
        note_dict[key.decode()]=value.decode()
    return note_dict

def _get_data(wave):
    labels=[a.decode() for a in wave['wave']['labels'][1] if a]
    col_indices={'rawz':labels.index('Raw'),
                 'defl':labels.index('Defl'),
                 'z':labels.index('ZSnsr')}
    wave_frame=pd.DataFrame(dict(rawz=wave['wave']['wData'][:,col_indices['rawz']],
                            z=wave['wave']['wData'][:,col_indices['z']],
                            defl=wave['wave']['wData'][:,col_indices['defl']]))
    return wave_frame

def load_ibw(filename):
    wave=bw.load(filename)
    data=_get_data(wave)
    notes=_get_notes(wave)
    trigger_index=np.argmax(data.loc[:,'defl'])

    sample_time=wave['wave']['wave_header']['sfA'][0]
    t=np.arange(data.shape[0])*sample_time
    data.loc[:,'t']=t

    dwell_time=float(notes['DwellTime'])
    dwell_start_time=data.loc[trigger_index,'t']
    dwell_end_time=dwell_start_time+dwell_time

    dwell_end_index=np.argmin(np.abs(data.loc[:,'t']-dwell_end_time))
    dwell_range=[trigger_index,dwell_end_index]
    k=float(notes['SpringConstant'])

    data.loc[:,'f']=data.loc[:,'defl']*k
    
    invOLS=float(notes['InvOLS'])

    this_curve=pylum.curves.Curve(filename=filename.split(os.path.sep)[-1],data=data,parameters=notes,z_col='z',t_col='t',f_col='f',invOLS=invOLS,k=k,dwell_range=dwell_range)

    
    return this_curve

def load_curveset_ibw(folder,ident_labels):
    ident_labels=tuple(ident_labels)
    regex_str=""
    for l in ident_labels:
        regex_str=regex_str+l+f'(?P<{l}>.*)'
    regex_str=regex_str+'\.ibw'
    regex=re.compile(regex_str)
    
    all_filenames=os.listdir(folder)
    all_matches=[regex.match(a) for a in all_filenames]

    curve_dict=dict()
    for m in all_matches:
        if not m:
            continue
        idents=tuple([m.group(a) for a in ident_labels])
        filename=m.group(0)
        filepath=os.path.join(folder,filename)
        curve_dict[idents]=load_ibw(filepath)

    this_curveset=pylum.curves.CurveSet(ident_labels=ident_labels,curve_dict=curve_dict)
    return this_curveset
