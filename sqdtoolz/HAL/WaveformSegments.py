import numpy as np
from sqdtoolz.HAL.WaveformTransformations import*

class WaveformSegmentBase:
    def __init__(self, name, transform_func, duration):
        self._name = name
        if transform_func:
            assert isinstance(transform_func, WaveformTransformationArgs), "Transformation function specified incorrectly - remember to call apply() on the WFMT object..."
        self._transform_func = transform_func
        self._duration = duration
        self._lab = None    #Should be set by the AWG class when required...

    @property
    def Name(self):
        return self._name

    def NumPts(self, fs):
        return int(np.round(self.Duration*fs))

    @property
    def Duration(self):
        return self._duration
    @Duration.setter
    def Duration(self, len_seconds):
        self._duration = len_seconds

    def reset_waveform_transforms(self):
        if self._transform_func:
            return self._lab.WFMT(self._transform_func.wfmt_name).initialise_for_new_waveform()

    def get_waveform(self, fs, t0_ind, ch_index):
        '''
        Returns the final waveform; that is, after applying the modification function.

        Inputs:
            - fs - Sample Rate in Hertz
            - t0_ind - Initial time (useful when the actual time in the waveform is important like with the phase of sinusoidal
                   modulation or perhaps a continual ramp/waveform that is to continue rather than resetting back to zero).
                   Note that t0 is given as the point index (0 for t=0 being the first point of the entire waveform).
            - ch_index - Dimension/index of the waveform; useful when the modification function is a function of dimnension
                         in ND waveforms.
        
        Returns a numpy array of points representing the total waveform.
        '''
        cur_wfm = self._get_waveform(fs, t0_ind, ch_index)
        #Transform if necessary:      
        if self._transform_func:
            return self._lab.WFMT(self._transform_func.wfmt_name).modify_waveform(cur_wfm, fs, t0_ind, ch_index, **self._transform_func.kwargs)
        else:
            return cur_wfm

    def _get_waveform(self, fs, t0_ind, ch_index):
        assert False, "Waveform Segment classes must implement a get_waveform function."

    def _get_current_config(self):
        '''
        Gets the current JSON-style configuration that can be used to reinstantiate this class. Note that the inherited
        daughter class should override and call this class and should implement the key 'type' along with other keys that
        can be used to reinstantiate the daughter class.
        '''
        cur_dict = {}
        cur_dict['Name'] = self.Name
        cur_dict['Type'] = self.__class__.__name__
        if self._transform_func == None:
            cur_dict['Mod Func'] = {'Name' : '', 'Args' : ''}
        else:
            cur_dict['Mod Func'] = {'Name' : self._transform_func.wfmt_name, 'Args' : self._transform_func.kwargs}
        return cur_dict

class WFS_Group(WaveformSegmentBase):
    def __init__(self, name, wfm_segs, time_len=-1, transform_func=None):
        super().__init__(name, transform_func, time_len)
        self._abs_time = time_len   #_abs_time is the total absolute time (if -1, the duration is the sum of the individual time segment durations)
        self._wfm_segs = wfm_segs
        self._validate_wfm_segs()

    @property
    def Duration(self):
        if self._abs_time == -1:
            return sum([x.Duration for x in self._wfm_segs])
        else:
            return self._abs_time
    @Duration.setter
    def Duration(self, len_seconds):
        self._abs_time = len_seconds
    
    def _validate_wfm_segs(self):
        elastic_segs = []
        for ind_wfm, cur_wfm_seg in enumerate(self._wfm_segs):
            if cur_wfm_seg.Duration == -1:
                elastic_segs += [ind_wfm]
        assert len(elastic_segs) <= 1, "There are too many elastic waveform segments (cannot be above 1)."
        if self._abs_time == -1:
            assert len(elastic_segs) == 0, "If the total waveform length is unbound, the number of elastic segments must be zero."
        if self._abs_time > 0 and len(elastic_segs) == 0:
            assert sum([x.Duration for x in self._wfm_segs]) == self._abs_time, "Sum of waveform segment durations do not match the total specified waveform group time. Consider making one of the segments elastic by setting its duration to be -1."
        
        #Return the elastic segment index
        if len(elastic_segs) > 0:
            return elastic_segs[0]
        else:
            return -1

    def _get_waveform(self, fs, t0_ind, ch_index):
        elas_seg_ind = self._validate_wfm_segs()
        
        #Calculate and set the elastic time segment
        if elas_seg_ind != -1:  #Note that self._abs_time > 0
            self._wfm_segs[elas_seg_ind].Duration = self._abs_time - (sum([x.Duration for x in self._wfm_segs])+1)    #Negate the -1 segment

        #Concatenate the individual waveform segments
        final_wfm = np.array([])
        t0_ind = 0
        for cur_wfm_seg in self._wfm_segment_list:
            #TODO: Preallocate - this is a bit inefficient...
            final_wfm = np.concatenate((final_wfms, cur_wfm_seg.get_waveform(self._sample_rate, t0_ind, ch_index)))
            t0_ind += final_wfm.size

        #Reset segment to be elastic
        if elas_seg_ind != -1:
            self._wfm_segs[elas_seg_ind].Duration = -1
        
        return final_wfm

class WFS_Constant(WaveformSegmentBase):
    def __init__(self, name, transform_func, time_len, value=0.0):
        super().__init__(name, transform_func, time_len)
        self._value = value

    @classmethod
    def fromConfigDict(cls, config_dict):
        assert 'Type' in config_dict, "Configuration dictionary does not have the key: type"
        assert config_dict['Type'] == cls.__name__, "Configuration dictionary has the wrong type."
        for cur_key in ["Name", "Duration", "Value"]:
            assert cur_key in config_dict, "Configuration dictionary does not have the key: " + cur_key
        #TODO: Fix the functionality here.
        if config_dict['Mod Func']['Name'] == '':
            wfmt_obj = None
        else:
            wfmt_obj = WaveformTransformationArgs(config_dict['Mod Func']['Name'], config_dict['Mod Func']['Args'])
        return cls(config_dict["Name"], wfmt_obj, config_dict["Duration"], config_dict["Value"])

    @property
    def Value(self):
        return self._value
    @Value.setter
    def Value(self, const_val):
        self._value = const_val

    def _get_waveform(self, fs, t0_ind, ch_index):
        return np.zeros(round(self.NumPts(fs))) + self._value

    def _get_current_config(self):
        cur_dict = WaveformSegmentBase._get_current_config(self)
        cur_dict['Duration'] = self.Duration
        cur_dict['Value'] = self._value
        return cur_dict

class WFS_Gaussian(WaveformSegmentBase):
    def __init__(self, name, transform_func, time_len, amplitude, num_sd=1.96):
        super().__init__(name, transform_func, time_len)
        #TODO: Add in a classmethod to use sigma and truncate...
        self._amplitude = amplitude
        self._num_sd = num_sd

    @classmethod
    def fromConfigDict(cls, config_dict):
        assert 'Type' in config_dict, "Configuration dictionary does not have the key: type"
        assert config_dict['Type'] == cls.__name__, "Configuration dictionary has the wrong type."
        for cur_key in ["Name", "Duration", "Amplitude", "Num SD"]:
            assert cur_key in config_dict, "Configuration dictionary does not have the key: " + cur_key
        #TODO: Fix the functionality here.
        if config_dict['Mod Func']['Name'] == '':
            wfmt_obj = None
        else:
            wfmt_obj = WaveformTransformationArgs(config_dict['Mod Func']['Name'], config_dict['Mod Func']['Args'])
        return cls(config_dict["Name"], wfmt_obj, config_dict["Duration"], config_dict["Amplitude"], config_dict["Num SD"])

    @property
    def Amplitude(self):
        return self._amplitude
    @Amplitude.setter
    def Amplitude(self, ampl_val):
        self._amplitude = ampl_val

    def _gauss(x):
        return np.exp(-x*x / (2*self._sigma*self._sigma))

    def _get_waveform(self, fs, t0_ind, ch_index):
        n = self.NumPts(fs)
        #Generate the sample points on the Gaussian (start and end points are the same)
        sample_points = np.linspace(-self._num_sd, self._num_sd, int(np.round(n)))
        #Now calculate the Gaussian along the sample points
        sample_points = np.exp(-sample_points*sample_points/2)
        #Now shift the end points such that they are at zero
        end_points = sample_points[0]
        sample_points = sample_points - end_points
        #Now normalise the height such that it is unity once more...
        sample_points = sample_points / (1-end_points)
        #Make the height the desired amplitude...
        return self._amplitude * sample_points

    def _get_current_config(self):
        cur_dict = WaveformSegmentBase._get_current_config(self)
        cur_dict['Duration'] = self.Duration
        cur_dict['Amplitude'] = self._amplitude
        cur_dict['Num SD'] = self._num_sd
        return cur_dict
