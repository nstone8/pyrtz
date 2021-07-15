import pickle

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

    def pickle(self,filename):
        with open(filename,'wb') as f:
            pickle.dump(self,f)

    def keys(self):
        return list(self.curve_dict.keys())

    def __getitem__(self,index):
        return self.curve_dict[index]
