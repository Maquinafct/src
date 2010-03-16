/* 2-D Fourier finite-difference wave extrapolation */
/*
  Copyright (C) 2008 University of Texas at Austin
  
  This program is free software; you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation; either version 2 of the License, or
  (at your option) any later version.
  
  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.
  
  You should have received a copy of the GNU General Public License
  along with this program; if not, write to the Free Software
  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
*/
#include <rsf.h>
#include <math.h>
#include <limits.h>
#include "abcpass.h"
#ifdef _OPENMP
#include <omp.h>
#endif
int main(int argc, char* argv[]) 
{
    int nx, nt, nkx, nkz,  ix, it, ikx, ikz, nz, iz, nb, nxb, nzb;
    float dt, dx, dkx, kx, dz, dkz, kz, tmpdt, pi=SF_PI;
    float **new,  **old,  **cur,  **uk, **dercur, **derold;
    float  **v, v0, a, b1, b2, w, g1, g2, *wb, c, vc; 
    sf_file out, vel, source;
    bool opt;    /* optimal padding */
   // #ifdef _OPENMP
   // int nth;
   // #endif
     

    sf_init(argc,argv);
    out = sf_output("out");
    vel = sf_input("vel");   /* velocity */
    source = sf_input("in");   /* source wavlet*/

//    if (SF_FLOAT != sf_gettype(inp)) sf_error("Need float input");
    if (SF_FLOAT != sf_gettype(vel)) sf_error("Need float input");
    if (SF_FLOAT != sf_gettype(source)) sf_error("Need float input");
    if (!sf_histint(vel,"n1",&nx)) sf_error("No n1= in input");
    if (!sf_histfloat(vel,"d1",&dx)) sf_error("No d1= in input");
    if (!sf_histint(vel,"n2",&nz)) sf_error("No n2= in input");
    if (!sf_histfloat(vel,"d2",&dz)) sf_error("No d2= in input");
  //  if (!sf_histint(inp,"n2",&nt)) sf_error("No n2= in input");
  //  if (!sf_histfloat(inp,"d2",&dt)) sf_error("No d2= in input");
    if (!sf_getbool("opt",&opt)) opt=true;
    /* if y, determine optimal size for efficiency */
    if (!sf_getfloat("dt",&dt)) sf_error("Need dt input");
    if (!sf_getint("nt",&nt)) sf_error("Need nt input");
    if (!sf_getint("nb",&nb)) nb=30;

    if (!sf_getfloat("c",&c)) c = 0.01; /*decaying parameter*/
    sf_putint(out,"n1",nx);
    sf_putfloat(out,"d1",dx);
//    sf_putfloat(out,"o1",x0);
    sf_putint(out,"n2",nz);
    sf_putfloat(out,"d2",dz);
    sf_putint(out,"n3",nt);
    sf_putfloat(out,"d3",dt);
    sf_putfloat(out,"o3",0.0); 

    nxb = nx + 2*nb;
    nzb = nz + 2*nb;
    nkx = nxb;
    nkz = nzb;
    dkx = 1./(2.0*kiss_fft_next_fast_size(nxb-1)*dx);
    dkz = 1./(2.0*kiss_fft_next_fast_size(nzb-1)*dz);



    old    =  sf_floatalloc2(nxb,nzb);
    cur    =  sf_floatalloc2(nxb,nzb);
    new    =  sf_floatalloc2(nxb,nzb);
    uk     =  sf_floatalloc2(nxb,nzb);
    derold    =  sf_floatalloc2(nxb,nzb);
    dercur    =  sf_floatalloc2(nxb,nzb);
    
    v = sf_floatalloc2(nxb,nzb);
    /*input & extend velocity model*/
    for (iz=nb; iz<nz+nb; iz++){
        sf_floatread(v[iz]+nb,nx,vel);
         for (ix=0; ix<nb; ix++){
             v[iz][ix] = v[iz][nb];
             v[iz][nx+nb+ix] = v[iz][nx+nb-1];
         }
    }     
    for (iz=0; iz<nb; iz++){
        for (ix=0; ix<nxb; ix++){
            v[iz][ix] = v[nb][ix];
            v[nz+nb+iz][ix] = v[nz+nb-1][ix];
        }
    }

    vc =0.0; /*RMS v*/
    v0 = -FLT_MAX; /*Maximum v*/
    for (iz=0; iz < nzb; iz++) {
        for (ix=0; ix < nxb; ix++) {
            vc += v[iz][ix]*v[iz][ix];
            if(v[iz][ix] > v0) v0 = v[iz][ix];
         }
    }
    vc = sqrtf(vc/(nxb*nzb));
 
    w = dt*dt*vc*vc;
    g1 = dt*dt*(vc*vc-v0*v0)/(12.0*dx*dx);
    g2 = dt*dt*(vc*vc-v0*v0)/(12.0*dz*dz);
    b1 = w*g1;
    b2 = w*g2;
    a  = w-2.0*b1-2.0*b2;

    wb =  sf_floatalloc(nb);
    abc_cal(0,nb,c,wb);


    for (iz=nb; iz<nz+nb; iz++){
        sf_floatread(cur[iz]+nb,nx,source);
         for (ix=0; ix<nb; ix++){
             cur[iz][ix] = cur[iz][nb]; /*left*/
             cur[iz][nx+nb+ix] = cur[iz][nx+nb-1]; /*right*/
         }
    }     
    for (iz=0; iz<nb; iz++){
        for (ix=0; ix<nxb; ix++){
            cur[iz][ix] = cur[nb][ix]; /*top*/
            cur[nz+nb+iz][ix] = cur[nz+nb-1][ix]; /*bottom*/
        }
    }
    for (iz=0; iz < nzb; iz++) {
        for (ix=0; ix < nxb; ix++) {
            old[iz][ix] =  0.0; 
            derold[iz][ix] =cur[iz][ix]/dt;
           }
         }
    for (iz=nb; iz<nz+nb; iz++){
        sf_floatwrite(cur[iz]+nb,nx,out);
    }
/*
    #ifdef _OPENMP
    #pragma omp parallel
   {nth = omp_get_num_threads();}
    sf_warning("using %d threads",nth);
    #endif
*/
    /* propagation in time */
    for (it=1; it < nt; it++) {

         for (iz=0; iz < nzb; iz++){
             for (ix=0; ix < nxb; ix++){ 
                  new[iz][ix] = 0.0; 
                  uk[iz][ix] = cur[iz][ix]; 
                }
         }  


/* compute u(kx,kz) */
         sf_cosft_init(nxb);
         for (iz=0; iz < nzb; iz++){
             /* Fourier transform x to kx */
             sf_cosft_frw(uk[iz],0,1);
         }
         sf_cosft_close();

         sf_cosft_init(nzb);
         for (ikx=0; ikx < nkx; ikx++){
             /* Fourier transform z to kz */
             sf_cosft_frw(uk[0],ikx,nxb);
         }
         sf_cosft_close();

/*    #ifdef _OPENMP
    #pragma omp parallel for private(ik,ix,x,k,tmp,tmpex,tmpdt) 
    #endif
*/

         for (ikz=0; ikz < nkz; ikz++) {
             kz = ikz* dkz*2.0*pi;

             for (ikx=0; ikx < nkx; ikx++) {
                 kx = ikx * dkx*2.0*pi;
                 tmpdt = 2.0*(cosf(v0*sqrtf(kx*kx+kz*kz)*dt)-1.0)/(v0*v0*dt*dt);
                 uk[ikz][ikx] = uk[ikz][ikx]*tmpdt;
             }

         }   
/* Inverse FFT*/
         sf_cosft_init(nzb);
         for (ikx=0; ikx < nkx; ikx++){
             /* Inverse Fourier transform kz to z */
             sf_cosft_inv(uk[0],ikx,nxb);
         }
         sf_cosft_close();
         sf_cosft_init(nxb);
         for (iz=0; iz < nzb; iz++){
             /* Inverse Fourier transform kx to x */
              sf_cosft_inv(uk[iz],0,1);
         }
         sf_cosft_close();

	 for (iz=1; iz < nzb-1; iz++) {  
	     for (ix=1; ix < nxb-1; ix++) {  
                 new[iz][ix]  = uk[iz][ix]*a
                              + (uk[iz][ix-1]+uk[iz][ix+1])*b1
                              + (uk[iz-1][ix]+uk[iz+1][ix])*b2;
             }
         }  
    
         new[0][0] = uk[0][0]*a + uk[0][1]*b1 + uk[1][0]*b2;
         new[0][nxb-1] = uk[0][nxb-1]*a + uk[0][nxb-2]*b1 + uk[1][nxb-1]*b2;
         new[nzb-1][0] = uk[nzb-1][0]*a + uk[nzb-1][1]*b1 + uk[nzb-2][0]*b2;
         new[nzb-1][nxb-1] = uk[nzb-1][nxb-1]*a + uk[nzb-1][nxb-2]*b1 + uk[nzb-2][nxb-1]*b2;
          
	 for (ix=1; ix < nxb-1; ix++) {  
             new[0][ix] = uk[0][ix]*a + (uk[0][ix-1]+uk[0][ix+1])*b1 + uk[1][ix]*b2;
             new[nz-1][ix] = uk[nz-1][ix]*a + (uk[nz-1][ix-1]+uk[nz-1][ix+1])*b1 + uk[nz-2][ix]*b2;
         }
	 for (iz=1; iz < nzb-1; iz++) {  
             new[iz][0] = uk[iz][0]*a + uk[iz][1]*b1 + (uk[iz-1][0]+uk[iz+1][0])*b2; 
             new[iz][nx-1] = uk[iz][nx-1]*a + uk[iz][nx-2]*b1 + (uk[iz-1][nx-1]+uk[iz+1][nx-1])*b2; 
         }
         
	 for (iz=0; iz < nzb; iz++) {  
             for (ix=0; ix < nxb; ix++) {
                 dercur[iz][ix]= derold[iz][ix] + new[iz][ix]/dt;
                 new[iz][ix] = cur[iz][ix] + dercur[iz][ix]*dt; 
             }
         }

                 
	 for (iz=0; iz < nb; iz++) {  
             for (ix=nb; ix < nx+nb; ix++) {
                 new[iz][ix] *= wb[iz];
                 new[iz+nb+nz][ix] *= wb[nb-1-iz];
                 dercur[iz][ix] *= wb[iz];
                 dercur[iz+nb+nz][ix] *= wb[nb-1-iz];
             }
         }
	 for (iz=nb; iz < nz+nb; iz++) {  
             for (ix=0; ix < nb; ix++) {
                 new[iz][ix] *= wb[ix];
                 new[iz][ix+nx+nb] *= wb[nb-1-ix]; 
                 dercur[iz][ix] *= wb[ix];
                 dercur[iz][ix+nx+nb] *= wb[nb-1-ix];
             }
         }
	 for (iz=0; iz < nb; iz++) {  
             for (ix=0; ix < nb; ix++) {
                 new[iz][ix] *= wb[ix>iz?ix:iz];
                 dercur[iz][ix] *= wb[ix>iz?ix:iz];
                 new[iz][ix+nx+nb] *= wb[iz>(nb-1-ix)?iz:(nb-1-ix)]; 
                 dercur[iz][ix+nx+nb] *= wb[iz>(nb-1-ix)?iz:(nb-1-ix)]; 
                 new[iz+nb+nz][ix] *= wb[ix>(nb-1-iz)?ix:(nb-1-iz)];
                 dercur[iz+nb+nz][ix] *= wb[ix>(nb-1-iz)?ix:(nb-1-iz)];
                 new[iz+nb+nz][ix+nb+nz] *= wb[ix<iz?(nb-1-ix):(nb-1-iz)];
                 dercur[iz+nb+nz][ix+nb+nz] *= wb[ix<iz?(nb-1-ix):(nb-1-iz)];
             }
         }
	 for (iz=0; iz < nzb; iz++) {  
             for(ix=0; ix < nxb; ix++) {
	        old[iz][ix] = cur[iz][ix]; 
	        cur[iz][ix] = new[iz][ix]; 
	        derold[iz][ix] = dercur[iz][ix]; 
             }
         }
         for (iz=nb; iz<nz+nb; iz++){
             sf_floatwrite(new[iz]+nb,nx,out);
         }  
    }
    free(*v);     
    free(*new);     
    free(*cur);     
    free(*old);     
    free(*dercur);     
    free(*derold);     
    free(*uk);     
    free(v);     
    free(new);     
    free(cur);     
    free(old);     
    free(dercur);     
    free(derold);     
    free(uk);     
 //   sf_fileclose(vel);
 //   sf_fileclose(inp);
 //   sf_fileclose(out);
 
    exit(0); 
}           
           
