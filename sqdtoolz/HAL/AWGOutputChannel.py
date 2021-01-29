import numpy as np

class AWGOutputChannel:
    def __init__(self, instr_awg, channel_name):
        self._instr_awg = instr_awg
        self._channel_name = channel_name
        self._instr_awg_chan = instr_awg._get_channel_output(channel_name)
        assert self._instr_awg_chan != None, "The channel name " + channel_name + " does not exist in the AWG instrument " + self._instr_awg.name

    @property
    def Name(self):
        return self._name

    @property
    def Amplitude(self):
        return self._instr_awg_chan.Amplitude
    @Amplitude.setter
    def Amplitude(self, val):
        self._instr_awg_chan.Amplitude = val
        
    @property
    def Offset(self):
        return self._instr_awg_chan.Offset
    @Offset.setter
    def Offset(self, val):
        self._instr_awg_chan.Offset = val
        
    @property
    def Output(self):
        return self._instr_awg_chan.Output
    @Output.setter
    def Output(self, boolVal):
        self.Output = boolVal

class AWGOutputMarker:
    def __init__(self, parent_waveform_obj):
        self._parent = parent_waveform_obj
        #Marker status can be Arbitrary, Segments, None, Trigger
        self._marker_status = 'Arbitrary'
        self._marker_pol = 1
        self._marker_arb_array = np.array([], dtype=np.ubyte)
        self._marker_seg_list = []
        self._marker_trig_delay = 0.0
        self._marker_trig_length = 1e-9
        
    def set_markers_to_segments(self, list_seg_names):
        self._marker_status = 'Segments'
        #Check the listed segments actually exist in the current list of WaveformSegment objects
        for cur_seg_name in list_seg_names:
            found_seg = None
            for cur_seg_chk in self._parent._wfm_segment_list:
                if cur_seg_chk.Name == cur_seg_name:
                    found_seg = cur_seg_chk
                    break
            assert found_seg != None, "WaveformSegment " + found_seg + " has not been added to this Waveform sequence."
        self._marker_seg_list = list_seg_names[:] #Copy over the list

    def set_markers_to_arbitrary(self, arb_mkr_list):
        self._marker_arb_array = arb_mkr_list[:]
    
    def set_markers_to_trigger(self):
        '''
        Enables one to set the markers via its associated Trigger object attributes.
        '''
        self._marker_status = 'Trigger'
    
    def set_markers_to_none(self):
        self._marker_status = 'None'

    @property
    def TrigPulseDelay(self):
        self._validate_trigger_parameters()
        return self._marker_trig_delay
    @TrigPulseDelay.setter
    def TrigPulseDelay(self, len_seconds):
        assert self._marker_status == 'Trigger', "Cannot manipulate the marker waveforms on an AWG channel like a Trigger pulse without being in Trigger mode (i.e. call set_markers_to_trigger)"
        self._marker_trig_delay = len_seconds

    @property
    def TrigPulseLength(self):
        self._validate_trigger_parameters()
        return self._marker_trig_length
    @TrigPulseLength.setter
    def TrigPulseLength(self, len_seconds):
        assert self._marker_status == 'Trigger', "Cannot manipulate the marker waveforms on an AWG channel like a Trigger pulse without being in Trigger mode (i.e. call set_markers_to_trigger)"
        self._marker_trig_length = len_seconds

    @property
    def TrigPolarity(self):
        return self._marker_pol
    @TrigPolarity.setter
    def TrigPolarity(self, pol):
        assert self._marker_status == 'Trigger', "Cannot manipulate the marker waveforms on an AWG channel like a Trigger pulse without being in Trigger mode (i.e. call set_markers_to_trigger)"
        self._marker_pol = pol

    @property
    def TrigEnable(self):
        return self._instrTrig.TrigEnable
    @TrigEnable.setter
    def TrigEnable(self, boolVal):
        assert self._marker_status == 'Trigger', "Cannot manipulate the marker waveforms on an AWG channel like a Trigger pulse without being in Trigger mode (i.e. call set_markers_to_trigger)"
        self._instrTrig.TrigEnable = boolVal

    def _validate_trigger_parameters(self):
        #Validation need not occur if in Trigger mode. But the other modes need to be checked if the marker
        #waveform satisfies a proper trigger waveform...
        if self._marker_status == 'Segments' or self._marker_status == 'Arbitrary':
            mkr_array = self._assemble_marker_raw()
            prev_val = mkr_array[0]
            changes = []
            for ind, cur_val in enumerate(mkr_array):
                if (cur_val != prev_val):
                    changes += [ind]
                    prev_val = cur_val
            assert len(changes) <= 2, "The marker waveform has too many changing edges to constitute a valid trigger"
            #Set the trigger parameters
            if mkr_array[0] == 0:
                self._marker_pol = 1
            else:
                self._marker_pol = 0
            if len(changes) == 0:
                self._marker_trig_delay = 0
                self._marker_trig_length = 0
            elif len(changes) == 1:
                self._marker_trig_delay = changes[0] * self._parent._sample_rate
                self._marker_trig_length = self.Duration - self._marker_trig_delay
            else:
                self._marker_trig_delay = changes[0] * self._parent._sample_rate
                self._marker_trig_length = changes[1] * self._parent._sample_rate - self._marker_trig_delay
        elif self._marker_status == 'None':
            self._marker_trig_delay = 0
            self._marker_trig_length = 0

    def _assemble_marker_raw(self):
        if self._marker_status == 'None':
            return np.array([], dtype=np.ubyte)

        if self._marker_status == 'Trigger':
            final_wfm = np.zeros(int(np.round(self._parent.NumPts)), dtype=np.ubyte) + 1 - self._marker_pol
            start_pt = int(np.round(self._marker_trig_delay * self._parent._sample_rate))
            end_pt = int(np.round((self._marker_trig_delay + self._marker_trig_length) * self._parent._sample_rate))
            final_wfm[start_pt:end_pt+1] = self._marker_pol
            return final_wfm
        elif self._marker_status == 'Arbitrary':
            return self._marker_arb_array
        elif self._marker_status == 'Segments':
            final_wfm = np.zeros(int(np.round(self._parent.NumPts)), dtype=np.ubyte) + 1 - self._marker_pol
            for cur_seg_name in self._marker_seg_list:
                start_pt, end_pt = self._parent._get_index_points_for_segment(cur_seg_name)
                final_wfm[start_pt:end_pt] = self._marker_pol
            return final_wfm