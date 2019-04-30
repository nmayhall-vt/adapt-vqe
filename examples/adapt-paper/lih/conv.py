from tVQE import *
import vqe_methods 
import operator_pools
import pyscf_helper
import openfermion
import scipy
import sys

import pyscf
from pyscf import lib
from pyscf import gto, scf, mcscf, fci, ao2mo, lo, molden, cc
from pyscf.cc import ccsd


from joblib import Parallel, delayed

def geom_point(f):
    r = 1.342
    geometry = [('H',   (0,0,-r*f)), 
                ('Be',  (0,0,0)), 
                ('H',   (0,0,r*f))]
    filename = "beh2_var_gsd_t9_r%04.3f.out" %f
    sys.stdout = open(filename, 'w')
    
    charge = 0
    spin = 0
    basis = 'sto-3g'
    [n_orb, n_a, n_b, h, g, mol, E_nuc, E_scf, C, S] = pyscf_helper.init(geometry,charge,spin,basis)
    sq_ham = pyscf_helper.SQ_Hamiltonian()
    sq_ham.init(h, g, C, S)
    
    print(" HF Energy: %12.8f" %(E_nuc + sq_ham.energy_of_determinant(range(n_a),range(n_b))))
    fermi_ham  = sq_ham.export_FermionOperator()
    
    hamiltonian = openfermion.transforms.get_sparse_operator(fermi_ham)
    
    s2 = vqe_methods.Make_S2(n_orb)
    
    #build reference configuration
    occupied_list = []
    for i in range(n_a):
        occupied_list.append(i*2)
    for i in range(n_b):
        occupied_list.append(i*2+1)
    
    print(" Build reference state with %4i alpha and %4i beta electrons" %(n_a,n_b), occupied_list)
    reference_ket = scipy.sparse.csc_matrix(openfermion.jw_configuration_state(occupied_list, 2*n_orb)).transpose()
    
    [e,v] = scipy.sparse.linalg.eigsh(hamiltonian.real,1,which='SA',v0=reference_ket.todense())
    for ei in range(len(e)):
        S2 = v[:,ei].conj().T.dot(s2.dot(v[:,ei]))
        print(" FCI State %4i: %12.8f au  <S2>: %12.8f" %(ei,e[ei]+E_nuc,S2))
    fermi_ham += openfermion.FermionOperator((),E_nuc)
    pyscf.molden.from_mo(mol, "full.molden", sq_ham.C)
    
    pool = operator_pools.spin_complement_GSD()
    pool.init(n_orb)
    
    
    [e,v,params] = vqe_methods.adapt_vqe(fermi_ham, pool, reference_ket, adapt_thresh=1e-6, theta_thresh=1e-9)
    
    print(" Final ADAPT-VQE energy: %12.8f" %e)
    print(" <S^2> of final state  : %12.8f" %(v.conj().T.dot(s2.dot(v))[0,0].real))

Parallel(n_jobs=20)(delayed(geom_point)(f/10+.5) for f in range(21))
