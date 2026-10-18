def recs(data,start=0,limit=None):
    i=start;n=0;L=len(data)
    while i<L:
        t=data[i];i+=1
        if t&0x80:
            t=(t&0x7f)|((data[i]&0x7f)<<7);i+=1
        s=0;sh=0
        for k in range(4):
            b=data[i];i+=1;s|=(b&0x7f)<<sh;sh+=7
            if not b&0x80: break
        yield t,i,s
        i+=s;n+=1
        if limit and n>=limit: return
