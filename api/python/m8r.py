##   Copyright (C) 2010 University of Texas at Austin
##  
##   This program is free software; you can redistribute it and/or modify
##   it under the terms of the GNU General Public License as published by
##   the Free Software Foundation; either version 2 of the License, or
##   (at your option) any later version.
##  
##   This program is distributed in the hope that it will be useful,
##   but WITHOUT ANY WARRANTY; without even the implied warranty of
##   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##   GNU General Public License for more details.
##  
##   You should have received a copy of the GNU General Public License
##   along with this program; if not, write to the Free Software
##   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
import os, sys, tempfile, re, subprocess, urllib

import numpy as np

try:
    import c_m8r as c_rsf
    _swig_ = True
except:
    _swig_ = False
#_swig_ = False   #kls allow temporary test of with old major path in the code
#sys.stderr.write('reset _swig_=%s\n'%repr(_swig_))

first_input=None

import rsf.doc
import rsf.prog
import rsf.path
import datetime
import tempfile

###
# Define the octal representations for End Of Line and 
#   End Of Transmission
SF_EOL=014
SF_EOT=004

def view(name):
    try:
        from IPython.display import Image
        png = name+'.png'
        makefile = os.path.join(rsf.prog.RSFROOT,'include','Makefile')
        os.system('make -f %s %s' % (makefile,png))
        return Image(filename=png)
    except:
        print 'No IPython Image support'
        return None

class Par(object):
    '''parameter table'''
    def __init__(self,argv=sys.argv):
        self.noArrays = True
        self.prog = argv[0]
        self.__args = self.__argvlist2dict(argv[1:])
    def __argvlist2dict(self,argv):
        """Eliminates duplicates in argv and makes it a dictionary"""
        argv = self.__filter_equal_sign(argv)
        args = {}
        for a in argv:
            key = a.split('=')[0]
            args[key] = a.replace(key+'=','')
        return args

    def __filter_equal_sign(self,argv):
        """Eliminates "par = val", "par= val" and "par =val" mistakes."""
        argv2 = []
        # Could not use the simpler 'for elem in argv'...argv.remove because
        # lonely '=' signs are treated weirdly. Many things did not work as
        # expected -- hence long and ugly code. Test everything.
        for i in range( len(argv) ):
            if argv[i] != '=':
                if argv[i].find('=') != 0:
                    if argv[i].find('=') != -1:
                        if argv[i].find('=') != len(argv[i])-1:
                            argv2.append(argv[i])
        return argv2

    def __get(self, key, default=None):
        """Obtains value of argument from dictionary"""
        # kls
        sys.stderr.write(
            'I think this function Par.__get function can be removed.\n')
        sys.stderr.write( 'Do you see this print?\n')
        if self.__args.has_key(key):
            return self.__args[key]
        else:
            return default
    
    # call without default then test if return is None is error
    # on a required parameter.  cannot tell difference between illegal
    # int value and value not input. 
    def int(self,key,default=None):
        """Returns integer argument given to program"""
        try:
            val=self.__args[key] 
        except:
            return default
            
        try:
            return int(val)
        except:
            sys.stderr.write('program reading command line arg %s\n'%key)
            sys.stderr.write('parsing %s=%s\n'%(key,val))
            sys.stderr.write('right of = sign must be an int\n')
            sys.stderr.write('error - exiting program\n')
            quit()

    def string(self, key, default=None):
        """Returns string argument given to program"""
        try:
            return self.__args[key]
        except:
            return default
                
    def float(self,key,default=None):
        """Returns float argument given to program"""
        try:
            val=self.__args[key] 
        except:
            return default

        try:
            return float(val )
        except:
            sys.stderr.write('program reading command line arg %s\n'%key)
            sys.stderr.write('parsing %s=%s\n'%(key,val))
            sys.stderr.write('right of = sign must be a float\n')
            sys.stderr.write('error - exiting program\n')
            quit()

    def bool(self,key,default=None):
        """Returns bool argument given to program"""
        try:
            val = self.__args[key]
        except:
            return default
        val = str(val).lower()
        if val[0] == 'y' or val == 'true':
            return True
        elif val[0] =='n' or val == 'false':
            return False
        else:
            return None

# default parameters for interactive runs
par = Par(['python','-'])

class Temp(str):
    'Temporaty file name'
    datapath = rsf.path.datapath()
    tmpdatapath = os.environ.get('TMPDATAPATH',datapath)
    def __new__(cls):
        return str.__new__(cls,tempfile.mktemp(dir=Temp.tmpdatapath))

class File(object):
    attrs = ['rms','mean','norm','var','std','max','min','nonzero','samples']
    def __init__(self,tag,temp=False,name=''):
        'Constructor'
        if isinstance(tag,File):
            # copy file (name is ignored)
            self.__init__(tag.tag)
            tag.close()
        else:
            self.tag = tag
        self.filename=self.tag
        self.temp = temp
        self.narray = None
        for filt in Filter.plots + Filter.diagnostic:
            # run things like file.grey() or file.sfin()
            setattr(self,filt,Filter(filt,srcs=[self],run=True))
        for attr in File.attrs:
            setattr(self,attr,self.want(attr))
    def __str__(self):
        'String representation'
        if self.tag:
            tag = str(self.tag)
            if os.path.isfile(tag):
                return tag
            else:
                raise TypeError, 'Cannot find "%s" ' % tag
        else:
            raise TypeError, 'Cannot find tag'
    def sfin(self):
        'Output of sfin'
        return Filter('in',run=True)(0,self)
    def want(self,attr):
        'Attributes from sfattr'
        def wantattr():
            try:
                val = os.popen('%s want=%s < %s' % 
                               (Filter('attr'),attr,self)).read()
            except:
                raise RuntimeError, 'trouble running sfattr'
            m = re.search('=\s*(\S+)',val)
            if m:
                val = float(m.group(1))
            else:
                raise RuntimeError, 'no match'
            return val
        return wantattr
    def real(self):
        'Take real part'
        re = Filter('real')
        return re[self]
    def cmplx(self,im):
        c = Filter('cmplx')
        return c[self,im]
    def imag(self):
        'Take imaginary part'
        im = Filter('imag')
        return im[self]
    def __add__(self,other):
        'Overload addition'
        add = Filter('add')
        return add[self,other]
    def __sub__(self,other):
        'Overload subtraction'
        sub = Filter('add')(scale=[1,-1])
        return sub[self,other]
    def __mul__(self,other):
        'Overload multiplication'
        try:
            mul = Filter('scale')(dscale=float(other))
            return mul[self]
        except:
            mul = Filter('mul')(mode='product')
            return mul[self,other]
    def __div__(self,other):
        'Overload division'
        try:
            div = Filter('scale')(dscale=1.0/float(other))
            return div[self]
        except:
            div = Filter('add')(mode='divide')
            return div[self,other]
    def __neg__(self):
        neg = Filter('scale')(dscale=-1.0) 
        return neg[self]
    def dot(self,other):
        'Dot product'
        # incorrect for complex numbers
        prod = self.__mul__(other)
        stack = Filter('stack')(norm=False,axis=0)[prod]
        return stack[0]
    def cdot2(self):
        'Dot product with itself'
        abs2 = Filter('math')(output="abs(input)").real[self]
        return abs2.dot(abs2)
    def dot2(self):
        'Dot product with itself'
        return self.dot(self)
    def __array__(self,context=None):
        'numpy array'
        if False and _swig_: #kls I broke path that uses c_rsf.sf_input
            if None == self.narray:
                if not hasattr(self,'f'):
                    f = c_rsf.sf_input(self.tag)
                else:
                    f = self.f
                self.narray = c_rsf.rsf_array(f)
                if not hasattr(self,'f'):
                    c_rsf.sf_fileclose(f)
            return self.narray
        else:
            # gets only the real part of complex arrays
            # should be able to dp something like this, which is used in 
            # class Input.read()
            #sys.stderr.write('in __array__\n')
            tempinput=Input(self.filename)
            #sys.stderr,write('call getall\n')
            return tempinput.getalldata()
            
    def __array_wrap__(self,array,context=None):
        inp = Input(self) 
        inp.read(array)
        return inp
    def __getitem__(self,i):
        array = self.__array__()
        return array[i]
    def __setitem__(self,index,value):
        array = self.__array__()
        array.__setitem__(index,value)
    def size(self,dim=0):
        return File.leftsize(self,dim)

    def leftsize(self,dim=0):
        s = 1
        for axis in range(dim+1,10):
            n = self.int("n%d" % axis)
            if n:
                s *= n
            else:
                break
        return s
    
    def int(self,key,default=None):
        try:
            p = subprocess.Popen('%s %s parform=n < %s' % 
                                 (Filter('get'),key,self),
                                 shell=True,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 close_fds=True)
            get = p.stdout.read()
        except:
            raise RuntimeError, 'trouble running sfget'
        if get:
            val = int(get)
        elif default:
            val = default
        else:
            val = None
        return val
    def shape(self):
        # axes are reversed for consistency with numpy
        s = []
        dim = 1
        for i in range(1,10):
            ni = self.int('n%d' % i)
            if ni:
                dim = i
            s.append(ni)
        s = s[:dim]
        # the trailing members of s that are 1 ie fix situations like
        # s=(1500,240,1,1)
        while s[-1]==1 and len(s)>1:
            s=s[:-1]
        s.reverse()
        return tuple(s)
    def reshape(self,shape=None):
        if not shape:
            shape = self.size()
        try:
            shape = list(shape)
        except:
            shape = [shape]
        old = list(self.shape())
        old.reverse()
        shape.reverse()
        lold = len(old)
        lshape = len(shape)
        puts = {}
        for i in range(max(lold,lshape)):
            ni = 'n%d' % (i+1)
            if i < lold:
                if i < lshape:
                    if old[i] != shape[i]:
                        puts[ni] = shape[i]
                else:
                    puts[ni] = 1
            else:
                puts[ni] = shape[i]
        put = Filter('put')
        put.setcommand(puts)
        return put[self]
    def __len__(self):
        return self.size()
    def close(self):
        if self.temp:
            Filter('rm',run=True)(0,self)
    def __del__(self):
        sys.stderr.write('Closing File\n')
        self.close()


class _File(File):
    type = ['uchar','char','int','float','complex']
    form = ['ascii','xdr','native']
    def __init__(self,tag):
        if not self.f:
            raise TypeError, 'Use Input or Output instead of File'
        File.__init__(self,tag)
        # kls 
        #if _swig_:
        #    self.type = _File.type[c_rsf.sf_gettype(self.f)]
        #    self.form = _File.form[c_rsf.sf_getform(self.f)]

    def tell(self):
        return self.f.tell()
    def close(self):
        self.f.close()
    def __del__(self):
        # check if user call to flush or close already cleaned up
        if not self.f.closed: 
            self.close()
        File.close(self) # this removes file if it is temporary

    def settype(self,type):
        if _swig_: # kls
            for i in xrange(len(_File.type)):
                if type == _File.type[i]:
                    self.type = type
                c_rsf.sf_settype (self.f,i)
        else:
            sys.stderr.write('function settype only available with swig')
            sys.exit(1)

    def setformat(self,format):
        if _swig_:
            c_rsf.sf_setformat(self.f,format)
        else:
            sys.stderr.write('function setformat only available with swig')
            sys.exit(1)

    def __get(self,func,key,default):
        get,par = func(self.f,key)
        if get:
            return par
        elif default:
            return default
        else:
            return None
    def __gets(self,func,key,num,default):
        pars = func(self.f,key,num)
        if pars:
            return pars
        elif default:
            return default
        else:
            return None
    def string(self,key):
        return c_rsf.sf_histstring(self.f,key)
    def int(self,key,default=None):
        return self.__get(c_rsf.sf_histint,key,default)
    def float(self,key,default=None):
        return self.__get(c_rsf.sf_histfloat,key,default)
    def ints(self,key,num,default=None):
        return self.__gets(c_rsf.histints,key,num,default)    
    def bytes(self):
        return c_rsf.sf_bytes(self.f)
    def put(self,key,val):
        if isinstance(val,int):
            c_rsf.sf_putint(self.f,key,val)
        elif isinstance(val,float):
            c_rsf.sf_putfloat(self.f,key,val)
        elif isinstance(val,str):
            c_rsf.sf_putstring(self.f,key,val)
        elif isinstance(val,list):
            if isinstance(val[0],int):
                c_rsf.sf_putints(self.f,key,val)
        
class Input(_File):
    def __init__(self,tag='in'):
        global first_input
        self.temp=None
        #sys.stderr.write('in File __init__ tag=%s\n'%tag)
        self.filename=tag
        if tag == 'in':
            self.f=sys.stdin
        else:
            try:
                self.f = open(str(tag),'r')
            except:
                sys.stderr.write("Cannot read from \"%s\"\n" % tag)
                sys.exit(1)
        # Strip off the header.  Save it as self.header so it can be 
        # copied to an output file

        end_of_file_reading_header=False
        self.header=""
        while True:
            line=self.f.readline(3)
            if len(line)==0:
                end_of_file_reading_header=True
                break
            if (SF_EOL==ord(line[0]) and 
                SF_EOL==ord(line[1]) and 
                SF_EOT==ord(line[2])):
                break
            if ('\n' !=line[0] and 
                '\n' !=line[1] and 
                '\n'  !=line[2]):
                # There must be more on this line
                restofline = self.f.readline()
            else:
                restofline=""
            self.header=self.header+line+restofline

        self.__create_variable_dictionary(self.header)

        if end_of_file_reading_header:
            self.f.close()  # close input file is not stdin 
            self.filename=self.string("in")
            self.f = open(self.filename,'r')
                
        # need to remember fileloc of beginning of data
        try:
            self.datastart=self.f.tell()
            self.pipe=False
        except:
            self.datastart=0
            self.pipe=True
        #sys.stderr.write('self.datastart=%d\n'%self.datastart)
                 
        # example:
        # f = open("temp", "rb")  
        # f.seek(256, os.SEEK_SET)  
        # read the rest of the file into numpy array :
        # x = np.fromfile(f, dtype=np.int)  

        try:
            data_format=self.vd['data_format']
            if data_format=='native_float':
                self.type='float'
                self.form='native'
                esize=4
                self.datatype=np.float32
            elif data_format=='native_complex':
                self.type='complex'
                self.form='native'
                esize=8
                self.datatype=np.complex64
            elif data_format=='native_int':
                self.type='int'
                self.form='native'
                esize=4
                self.datatype=np.int32
            else:
                sys.stderr.write('error reading from input file.\n')
                sys.stderr.write('data_format=%s\n'%data_format)
                sys.stderr.write('filename=%s.\n',self.filename)
                sys.stderr.write('data_format must be native_float, '+
                                 'native_complex or native_int\n')
                sys.stderr.write('error - exiting program\n')
                quit()
        except:
            sys.stderr.write('error reading from input file.\n')
            sys.stderr.write('data_format is not defined\n')
            sys.stderr.write('filename=%s.\n',self.filename)
            sys.stderr.write('error - exiting program\n')
            quit()
            #kls write code to compute self.shape
        if first_input==None:
            first_input=self
                    
        File.__init__(self,tag)
        self.copy = False

    def __create_variable_dictionary(self, header):
        'Parse RSF header into a dictionary of variables'
        self.vd={} # variable dictionary
        ilist = header.split()
        # kls (karls mark).  this code should be shared with 
        # Par.__argvlist2dic__.  I think codes trap different errors.
        pos = 0
        squot = "'"
        dquot = '"'
        while pos < len(ilist):
            if '=' in ilist[pos]:
                tokenlist = ilist[pos].split('=')
 		if len(tokenlist[1]) == 0:
                    tokenlist[1]='""'
                lhs = tokenlist[0]
                rhs = tokenlist[1]
                quotmark = None
                if rhs[0] in (squot, dquot):
                    if rhs[0] == squot:
                        quotmark = squot
                    else:
                        quotmark = dquot
                    if rhs[-1] == quotmark:
                        rhs_out = rhs.strip(quotmark)
                        pos += 1
                    else:
                        rhs_out = rhs.lstrip(quotmark)
                        while pos < len(ilist):
                            pos += 1
                            rhs_out += ' '
                            if ilist[pos][-1] == quotmark:
                                rhs_out += ilist[pos][:-1]
                                break
                            else:
                                rhs_out += ilist[pos]
                else:
                    rhs_out = rhs
                    pos += 1
                self.vd[lhs] = rhs_out
            else:
                pos += 1

    def read(self,data):

        shape=data.shape
        datacount=data.size
        data=data.reshape(datacount)
        data[:]=np.fromfile(self.f,dtype=self.datatype,count=datacount)
        data=data.reshape(shape)
        return
        # kls update to allow reading part of input data
        # add readshape parameter. if not input use self.shape()

    def gettrace(self):
        datacount=self.shape()[-1]
        data=np.fromfile(self.f,dtype=self.datatype,count=datacount)
        return data

    def getalldata(self):
        datacount=self.leftsize()
        data=np.fromfile(self.f,dtype=self.datatype,count=datacount)
        data=data.reshape(self.shape())
        return data

    def get_tah(self):
        #sys.stderr.write("in get_tah(self)\n")
        temp=np.fromfile(self.f,dtype='int8',count=4)
        if temp.size !=4:
            return (True,None,None)
    
        type_input_record=temp.tostring().decode()
        #sys.stderr.write("type_input_record=%s\n"%type_input_record)
    
        #read the length of the trace+header
        fromfilearray=np.fromfile(self.f,dtype=np.int32,count=1);
        if fromfilearray.size != 1:
            return (True, None, None)
        input_record_length=fromfilearray[0];

        n1_traces=self.int('n1_traces')
        #sys.stderr.write('n1_traces=%s\n'%repr(n1_traces))

        trace=np.fromfile(self.f,dtype=self.datatype,count=n1_traces)
        if trace.size != n1_traces:
            return (True, None, None)
    
        header_format=self.string('header_format')
        esize=self.int('esize')

        headertype="unknown"
        if (header_format == 'native_float' and 
            esize == 4):
            headertype=np.float32

        if (header_format == 'native_complex' and 
            esize == 8):
            headertype=np.complex64

        if (header_format == 'native_int' and 
            esize == 4):
            headertype=np.int32

        n1_headers=self.int('n1_headers')
        #sys.stderr.write('n1_headers=%s\n'%repr(n1_headers))
        if headertype != "unknown":
            #sys.stderr.write('Input.read size=%s\n'%str(n1_headers))
            header=np.fromfile(self.f,dtype=headertype,count=n1_headers)
            if header.size != n1_headers:
                return (True, None, None)

        else:
            sys.stderr.write('error reading from input file.\n')
            sys.stderr.write('headertype unknown\n')
            sys.stderr.write('filename=%s.\n',self.filename)
            sys.stderr.write('data_format='+repr(header_format)+'\n')
            sys.stderr.write('esize='+repr(esize)+'\n')
            sys.stderr.write('error - exiting program\n')
            quit()

        return (False,trace,header)

    def get_segy_keyindx(self,keyname):
        standard_segy_key=['tracl', 'tracr', 'fldr', 'tracf', 'ep', 
                           'cdp', 'cdpt', 'trid', 'nvs', 'nhs',
                           'duse', 'offset', 'gelev', 'selev', 'sdepth',
                           'gdel', 'sdel', 'swdep', 'gwdep', 'scalel',
                           'scalco', 'sx', 'sy', 'gx', 'gy',
                           'counit', 'wevel', 'swevel', 'sut', 'gut',
                           'sstat', 'gstat', 'tstat', 'laga', 'lagb', 
                           'delrt', 'muts', 'mute', 'ns', 'dt', 
                           'gain', 'igc', 'igi', 'corr', 'sfs', 
                           'sfe', 'slen', 'styp', 'stas', 'stae', 
                           'tatyp', 'afilf', 'afils', 'nofilf', 'nofils', 
                           'lcf', 'hcf', 'lcs', 'hcs', 'year', 
                           'day', 'hour', 'minute', 'sec', 'timbas', 
                           'trwf', 'grnors', 'grnofr', 'grnlof', 'gaps', 
                           'otrav', 'cdpx', 'cdpy', 'iline', 'xline', 
                           'shnum', 'shsca', 'tval', 'tconst4', 'tconst2', 
                           'tunits','device', 'tscalar', 'stype', 'sendir', 
                           'unknown','smeas4','smeas2', 'smeasu', 'unass1', 
                           'unass2']
        # first look for keyname in the standard_segy_key list.  If not 
        # found, look in the input file header. If user invests new header
        # name or misspells name and there is conflict with input file 
        # header parm names, there will be confusion. 
        try:
            keyindx=standard_segy_key.index(keyname)
        except:
            keyindx=self.int(name)
        return keyindx

    def string(self, nm):
        try:
            return self.vd[nm]
        except:
            return None

    def int(self, nm):
        try:
            return int(self.vd[nm])
        except:
            return None

    def float(self, nm):
        try:
            return float(self.vd[nm])
        except:
            return None

    def close(self):
        # kls
        #if not self.copy:
        #    c_rsf.sf_fileclose(self.f)
        _File.close(self)

class Output(_File):
    def __init__(self,tag='out',src=None):
        self.temp=None
        if src==None :
            if first_input==None:
                self.header=""
            else:
                self.header=first_input.header
        else:
            self.header=src.header

        # kls create dictionary from src file
        #sys.stderr.write('in Output.__init__ check tag\n') 
        if tag == 'out':
            self.f=sys.stdout
            self.pipe=self.is_pipe()
            self.filename=self.getfilename()
            if self.filename==None:
                # cannot find the fine name. Probably in another directory
                # make up a temporary name
                datapath = os.environ.get('DATAPATH','.')
                temp_fd,temp_name =tempfile.mkstemp('',
                                                    sys.argv[0],
                                                    dir=datapath)
                os.close(temp_fd)
                self.filename=temp_name[len(datapath):]
                #sys.stderr.write("temp_name=%s\n"%temp_name)
                #sys.stderr.write("filename=%s\n"%self.filename)
        else:
            self.filename=tag
            self.f=open(self.filename,'w')
            self.pipe=False
        if not self.pipe:
            if self.filename == '/dev/null':
                self.filename = 'stdout'
                self.pipe=True
                sys.stderr.write('output is /dev/null')
            else:
                datapath = os.environ.get('DATAPATH','.')
                # prepend datapath and append @ to filename
                self.filename=datapath+'/'+self.filename+'@'
                #self.stream=sys.stdout.fileno()

        self.headerflushed = False

        # create a variable dictionary
        self.vd={}
        #sys.stderr.write('end Output.__init__ self.pipe=%s\n'%self.pipe)

    def tell(self):
        sys.stderr.write('in m8r.py Output.tell\n')
        sys.stderr.write('I do not think this function is required.\n')
        sys.stderr.write('you can just use self.f.tell()\n')
        return self.f.tell()

    def is_pipe(self):
        try:
            self.f.tell()
            return False
        except:
            return True

    def getfilename(self):
        f_fstat=os.fstat(self.f.fileno())
        #kls sys.stderr.write('f_fstat=%s\n'%repr(f_fstat))

        for filename in os.listdir('.'):
            if os.path.isfile(filename):
                if os.stat(filename).st_ino == f_fstat.st_ino:
                    return filename

        f_dev_null=open('/dev/null','w');
        f_dev_stat=os.fstat(f_dev_null.fileno())
        if f_dev_stat.st_ino == f_fstat.st_ino:
            return '/dev/null'

        return None 
 
    def put(self,key,value):
        # repr make string representation of an object
        if isinstance(value,str):
            #make sure string is inclosed in ".." in the .rsf file
            self.vd[key]='"'+value+'"'
        else:
            self.vd[key]="%s"%repr(value)

    def write(self,data):
        if not self.headerflushed:
            #sys.stderr.write('Output.write add datatype to file header\n')
            #sys.stderr.write('data.dtype=%s\n'%repr(data.dtype))
            if data.dtype==np.float32:
                self.put('data_format','native_float')
            if data.dtype==np.complex64:
                self.put('data_format','native_complex')
            if data.dtype==np.int32:
                self.put('data_format','native_int')
            #sys.stderr.write("flushheader in Output.write\n")
            self.flushheader(first_input)
        # kls should check array data type matches file data_format
        data.tofile(self.f)

    def put_tah(self,trace,header):
        if not self.headerflushed:
            if trace.dtype==np.float32:
                self.put('data_format','native_float')
            if trace.dtype==np.complex64:
                sys.stderr.write('error: python Output.put_tah does\n')
                sys.stderr.write('       support complex traces\n')
                # if you want to add this fix esize below
                quit()
                self.put('data_format','native_complex')
            if trace.dtype==np.int32:
                self.put('data_format','native_int')

            if header.dtype==np.float32:
                self.put('header_format','native_float')
            if header.dtype==np.complex64:
                sys.stderr.write('error: cannot use complex headrs\n')
                quit()
                self.put('header_format','native_complex')
            if header.dtype==np.int32:
                self.put('header_format','native_int')
            self.flushheader(first_input)
        # kls check array data type matches file data_format
        #temp=np.array([116,  97, 104,  32], dtype=np.int8)
        temp=np.array('tah ',dtype=str)
        temp.tofile(self.f)
        esize=4 #kls limitted to 4 byte entries
        temp=np.array([(trace.size+header.size)*esize],dtype=np.int32)
        temp.tofile(self.f)
        trace.tofile(self.f)
        header.tofile(self.f)

    def close(self):
        self.f.flush()
        if not self.pipe:
            self.f.close()

    def flushheader(self,src):
        # write the header (saved from the previous (input) file
        self.f.write(self.header)
        self.headerflushed = True
        #kls write command to output file 
        # kls check file.c sf_fileflush for examples
                
        # kls now write the command name and parameters
        self.f.write('\n# execute: ')
        for arg in sys.argv:
            self.f.write(arg+' ')
        self.f.write('\n')
        self.f.write('# time=%s\n'%datetime.datetime.now())
        self.f.write('\n')

        # kls now write the dictionary
        for key in self.vd:
            self.f.write("%s=%s\n"%(key,self.vd[key]))

        #sys.stderr.write('in flushheader test self.pipe\n')
        if self.pipe:
            #sys.stderr.write('in flushheader self.pipe==True\n')
            self.f.write('in="stdout"\n')
            self.f.write('in="stdin"\n')
            self.f.write("%s%s%s"%(chr(SF_EOL),chr(SF_EOL),chr(SF_EOT)))
        else:
            #sys.stderr.write('self.pipe==False\n')
            self.f.write('in="%s"\n'%self.filename)
            self.f.flush()
            self.f.close()
            self.f=open(self.filename,"w")

dataserver = os.environ.get('RSF_DATASERVER',
                            'http://www.reproducibility.org')

def Fetch(directory,filename,server=dataserver,top='data'):
    'retrieve a file from remote server'
    if server == 'local':
        remote = os.path.join(top,
                            directory,os.path.basename(filename))
        try:
            os.symlink(remote,filename)
        except:
            print 'Could not link file "%s" ' % remote
            os.unlink(filename)
    else:
        rdir =  os.path.join(server,top,
                             directory,os.path.basename(filename))
        try:
            urllib.urlretrieve(rdir,filename)
        except:
            print 'Could not retrieve file "%s" from "%s"' % (filename,rdir)
        
class Filter(object):
    'Madagascar filter'
    plots = ('grey','contour','graph','contour3',
             'dots','graph3','thplot','wiggle','grey3')
    diagnostic = ('attr','disfil')
    def __init__(self,name,prefix='sf',srcs=[],
                 run=False,checkpar=False,pipe=False):
        rsfroot = rsf.prog.RSFROOT
        self.plot = False
        self.stdout = True
        self.prog = None
        if rsfroot:
            lp = len(prefix)
            if name[:lp] != prefix:
                name = prefix+name
            self.prog = rsf.doc.progs.get(name)   
            prog = os.path.join(rsfroot,'bin',name)
            if os.path.isfile(prog):
                self.plot   = name[lp:] in Filter.plots
                self.stdout = name[lp:] not in Filter.diagnostic
                name = prog
        self.srcs = srcs
        self.run=run
        self.command = name
        self.checkpar = checkpar
        self.pipe = pipe
        if self.prog:
            self.__doc__ =  self.prog.text(None)
    def getdoc():
        '''for IPython'''
        return self.__doc__
    def _sage_argspec_():
        '''for Sage'''
        return None
    def __wrapped__():
        '''for IPython'''
        return None
    def __str__(self):
        return self.command
    def __or__(self,other):
        'pipe overload'
        self.command = '%s | %s' % (self,other) 
        return self
    def setcommand(self,kw,args=[]):
        parstr = []
        for (key,val) in kw.items():
            if self.checkpar and self.prog and not self.prog.pars.get(key):
                sys.stderr.write('checkpar: No %s= parameter in %s\n' % 
                                 (key,self.prog.name))
            if isinstance(val,str):
                val = '\''+val+'\''
            elif isinstance(val,File):
                val = '\'%s\'' % val
            elif isinstance(val,bool):
                if val:
                    val = 'y'
                else:
                    val = 'n'
            elif isinstance(val,list):
                val = ','.join(map(str,val))
            else:
                val = str(val)
            parstr.append('='.join([key,val]))
        self.command = ' '.join([self.command,
                                 ' '.join(map(str,args)),
                                 ' '.join(parstr)])
    def __getitem__(self,srcs):
        'Apply to data'
        mysrcs = self.srcs[:]
        if isinstance(srcs,tuple):
            mysrcs.extend(srcs)
        elif srcs:
            mysrcs.append(srcs)

        if self.stdout:
            if isinstance(self.stdout,str):
                out = self.stdout
            else:
                out = Temp()
            command = '%s > %s' % (self.command,out)
        else:
            command = self.command

        (first,pipe,second) = command.partition('|')
            
        if mysrcs:    
            command = ' '.join(['< ',str(mysrcs[0]),first]+
                               map(str,mysrcs[1:])+[pipe,second])  
                
        fail = os.system(command)
        if fail:
            raise RuntimeError, 'Could not run "%s" ' % command

        if self.stdout:
            if self.plot:
                return Vplot(out,temp=True)
            else:
                return File(out,temp=True)
    def __call__(self,*args,**kw):
        if args:
            self.stdout = args[0]
            self.run = True
        elif not kw and not self.pipe:
            self.run = True
        self.setcommand(kw,args[1:])
        if self.run:
            return self[0]
        else:
            return self
    def __getattr__(self,attr):
        'Making pipes'
        other = Filter(attr)
        self.pipe = True
        self.command = '%s | %s' % (self,other)
        return self

def Vppen(plots,args):
    name = Temp()
    os.system('vppen %s %s > %s' % (args,' '.join(map(str,plots)),name))
    return Vplot(name,temp=True)

def Overlay(*plots):
    return Vppen(plots,'erase=o vpstyle=n')

def Movie(*plots):
    return Vppen(plots,'vpstyle=n')

def SideBySide(*plots,**kw):
    n = len(plots)
    iso = kw.get('iso')
    if iso:
        return Vppen(plots,'size=r vpstyle=n gridnum=%d,1' % n)
    else:
        return Vppen(plots,'yscale=%d vpstyle=n gridnum=%d,1' % (n,n))

def OverUnder(*plots,**kw):
    n = len(plots)
    iso = kw.get('iso')
    if iso:
        return Vppen(plots,'size=r vpstyle=n gridnum=1,%d' % n)
    else:
        return Vppen(plots,'xscale=%d vpstyle=n gridnum=1,%d' % (n,n))

class Vplot(object):
    def __init__(self,name,temp=False,penopts=''):
        'Constructor'
        self.name = name
        self.temp = temp
        self.img = None
        self.penopts = penopts+' '
    def __del__(self):
        'Destructor'
        if self.temp:
            try:
                os.unlink(self.name)
            except:
                raise RuntimeError, 'Could not remove "%s" ' % self
    def __str__(self):
        return self.name
    def __mul__(self,other):
        return Overlay(self,other)
    def __add__(self,other):
        return Movie(self,other)
    def show(self):
        'Show on screen'
        os.system('sfpen %s' % self.name)
    def hard(self,printer='printer'):
        'Send to printer'
        os.system('PRINTER=%s pspen %s' % (printer,self.name))
    def image(self):
        'Convert to PNG in the current directory (for use with IPython and SAGE)'
        self.img = os.path.basename(self.name)+'.png'
        self.export(self.img,'png',args='bgcolor=w')
    def _repr_png_(self): 	 
        'return PNG representation' 	 
        if not self.img: 	 
            self.image() 	 
        img = open(self.img,'rb') 	 
        guts = img.read() 	 
        img.close() 	 
        return guts

    try:
        from IPython.display import Image
        
        @property
        def png(self):
            return Image(self._repr_png_(), embed=True)
    except:
        pass
        
    def movie(self):
        'Convert to animated GIF in the current directory (for use with SAGE)'
        self.gif = os.path.basename(self.name)+'.gif'
        self.export(self.gif,'gif',args='bgcolor=w')
    def export(self,name,format=None,pen=None,args=''):
        'Export to different formats'
        from rsf.vpconvert import convert
        if not format:
            if len(name) > 3:
                format = name[-3:].lower()
            else:
                format = 'vpl'
        convert(self.name,name,format,pen,self.penopts+args,verb=False)

class _Wrap(object):
     def __init__(self, wrapped):
         self.wrapped = wrapped
     def __getattr__(self, name):
         try:
             return getattr(self.wrapped, name)
         except AttributeError:
             if name in rsf.doc.progs.keys() or 'sf'+name in rsf.doc.progs.keys():
                 return Filter(name)
             else:
                 raise

sys.modules[__name__] = _Wrap(sys.modules[__name__])


if __name__ == "__main__":
    import numpy as np

#      a=100 Xa=5
#      float=5.625 cc=fgsg
#      dd=1,2x4.0,2.25 true=yes false=2*no label="Time (sec)"
    
    # Testing getpar
    sys.stderr.write('par=Par...\n')
#    this is original Par.  none of this works with _swig_=True
#    par = Par(["prog","a=5","b=as","a=100","par=%s" % sys.argv[0]])
    par = Par(["prog","a=5","b=as","a=100","float=5.625",
               "true=y","par=%s" % sys.argv[0]])
    sys.stderr.write('start test asserts\n')
    assert 100 == par.int("a")
    assert not par.int("c")
    assert 10 == par.int("c",10)
    assert 5.625 == par.float("float")
    assert par.bool("true")
    sys.stderr.write('label=%s\n'%par.string("label"))
    #assert "Time (sec)" == par.string("label")
    #assert "Time (sec)" == par.string("label","Depth")
    sys.stderr.write('nolabel=%s\n'%repr(par.string("nolabel")))
    assert not par.string("nolabel")
    sys.stderr.write('nolabel,Depth=%s\n'%repr(par.string("nolabel","Depth")))
    assert "Depth" == par.string("nolabel","Depth")
    # no function for this   par.close()
    # Testing file
    # Redirect input and output
    inp = os.popen("sfspike n1=100 d1=0.25 nsp=2 k1=1,10 label1='Time'")
    out = open("junk.rsf","w")
    os.dup2(inp.fileno(),sys.stdin.fileno())
    os.dup2(out.fileno(),sys.stdout.fileno())
    # Initialize
    par = Par()
    input = Input()
    output = Output()
    # Test
    assert 'float' == input.type
    assert 'native' == input.form
    n1 = input.int("n1")
    assert 100 == n1
    assert 0.25 == input.float("d1")
    assert 'Time' == input.string("label1")
    n2 = 10
    output.put('n2',n2)
#    assert 10 == output.int('n2') No Output.int. Why get from output? karl
    output.put('label2','Distance (kft)')
#    input.put("n",[100,100]) # No Input.put.  Why put to input? karl
#    assert [100,100] == input.ints("n",2)
    trace = np.zeros(n1,'f')
    input.read(trace)
    for i in xrange(n2):
        output.write(trace)
    os.system("sfrm junk.rsf")
