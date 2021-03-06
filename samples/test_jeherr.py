from TensorMol import *
import time
import random
PARAMS["max_checkpoints"] = 3
os.environ["CUDA_VISIBLE_DEVICES"]="0"

# Takes two nearly identical crystal lattices and interpolates a core/shell structure, must be oriented identically and stoichiometric
def InterpolateGeometries():
	a=MSet('cspbbr3_tess')
	#a.ReadGDB9Unpacked(path='/media/sdb2/jeherr/TensorMol/datasets/cspbbr3/pb_tess_6sc/')
	#a.Save()
	a.Load()
	mol1 = a.mols[0]
	mol2 = a.mols[1]
	mol2.RotateX()
	mol1.AlignAtoms(mol2)
	optimizer = Optimizer(None)
	optimizer.Interpolate_OptForce(mol1, mol2)
	mol1.WriteXYZfile(fpath='./results/cspbbr3_tess', fname='cspbbr3_6sc_pb_tess_goopt', mode='w')
	# mol2.WriteXYZfile(fpath='./results/cspbbr3_tess', fname='cspbbr3_6sc_ortho_rot', mode='w')

def ReadSmallMols(set_="SmallMols", dir_="/media/sdb2/jeherr/TensorMol/datasets/small_mol_dataset/*/*/", energy=False, forces=False, charges=False, mmff94=False):
	import glob
	a=MSet(set_)
	for dir in glob.iglob(dir_):
		a.ReadXYZUnpacked(dir, has_force=forces, has_energy=energy, has_charge=charges, has_mmff94=mmff94)
	print len(a.mols), " Molecules"
	a.Save()

def read_unpacked_set(set_name="chemspider12", paths="/media/sdb2/jeherr/TensorMol/datasets/chemspider12/*/", properties=["name", "energy", "gradients", "dipole"]):
	import glob
	a=MSet(set_name)
	for path in glob.iglob(paths):
		a.read_xyz_set_with_properties(paths, properties)
	print len(a.mols), " Molecules"
	a.Save()

def TrainKRR(set_ = "SmallMols", dig_ = "GauSH", OType_ ="Force"):
	a=MSet("SmallMols_rand")
	a.Load()
	TreatedAtoms = a.AtomTypes()
	d = Digester(TreatedAtoms, name_=dig_,OType_ =OType_)
	tset = TensorData(a,d)
	tset.BuildTrainMolwise("SmallMols",TreatedAtoms)
	manager=TFManage("",tset,True,"KRR_sqdiff")
	return

def RandomSmallSet(set_, size_):
	""" Returns an MSet of random molecules chosen from a larger set """
	print "Selecting a subset of "+str(set_)+" of size "+str(size_)
	a=MSet(set_)
	a.Load()
	b=MSet(set_+"_rand")
	mols = random.sample(range(len(a.mols)), size_)
	for i in mols:
		b.mols.append(a.mols[i])
	b.Save()
	return b

def BasisOpt_KRR(method_, set_, dig_, OType = None, Elements_ = []):
	""" Optimizes a basis based on Kernel Ridge Regression """
	a=MSet(set_)
	a.Load()
	TreatedAtoms = a.AtomTypes()
	dig = Digester(TreatedAtoms, name_=dig_, OType_ = OType)
	eopt = EmbeddingOptimizer(method_, a, dig, OType, Elements_)
	eopt.PerformOptimization()
	return

def BasisOpt_Ipecac(method_, set_, dig_):
	""" Optimizes a basis based on Ipecac """
	a=MSet(set_)
	a.Load()
	print "Number of mols: ", len(a.mols)
	TreatedAtoms = a.AtomTypes()
	dig = MolDigester(TreatedAtoms, name_=dig_, OType_ ="GoForce")
	eopt = EmbeddingOptimizer("Ipecac", a, dig, "radial")
	eopt.PerformOptimization()
	return

def TestIpecac(dig_ = "GauSH"):
	""" Tests reversal of an embedding type """
	a=MSet("OptMols")
	a.ReadXYZ("OptMols")
	m = a.mols[1]
	print m.atoms
	# m.WriteXYZfile("./results/", "Before")
	goodcrds = m.coords.copy()
	m.BuildDistanceMatrix()
	gooddmat = m.DistMatrix
	print "Good Coordinates", goodcrds
	TreatedAtoms = m.AtomTypes()
	dig = MolDigester(TreatedAtoms, name_=dig_, OType_ ="GoForce")
	emb = dig.Emb(m, MakeOutputs=False)
	m.Distort()
	ip = Ipecac(a, dig, eles_=[1,6,7,8])
	# m.WriteXYZfile("./results/", "Distorted")
	bestfit = ip.ReverseAtomwiseEmbedding(emb, atoms_=m.atoms, guess_=m.coords,GdDistMatrix=gooddmat)
	# bestfit = ReverseAtomwiseEmbedding(dig, emb, atoms_=m.atoms, guess_=None,GdDistMatrix=gooddmat)
	# print bestfit.atoms
	print m.atoms
	# bestfit.WriteXYZfile("./results/", "BestFit")
	return

def TestOCSDB(dig_ = "GauSH", net_ = "fc_sqdiff"):
	"""
	Test John Herr's first Optimized Force Network.
	OCSDB_test contains good crystal structures.
	- Evaluate RMS forces on them.
	- Optimize OCSDB_Dist02
	- Evaluate the relative RMS's of these two.
	"""
	tfm=TFManage("SmallMols_20rot_"+dig_+"_"+net_,None,False)
	a=MSet("OCSDB_Dist02_opt")
	a.ReadXYZ()
	b=MSet("OCSDB_Dist02_opt_test")
	b.mols = copy.deepcopy(a.mols)
	for m in b.mols:
		m.Distort(0.1)
	print "A,B RMS (Angstrom): ",a.rms(b)
	frcs = np.zeros(shape=(1,3))
	for m in a.mols:
		frc = tfm.EvalRotAvForce(m, RotAv=PARAMS["RotAvOutputs"], Debug=False)
		frcs=np.append(frcs,frc,axis=0)
	print "RMS Force of crystal structures:",np.sqrt(np.sum(frcs*frcs,axis=(0,1))/(frcs.shape[0]-1))
	b.name = "OCSDB_Dist02_OPTd"
	optimizer  = Optimizer(tfm)
	for i,m in enumerate(b.mols):
		m = optimizer.OptTFRealForce(m,str(i))
	b.WriteXYZ()
	print "A,B (optd) RMS (Angstrom): ",a.rms(b)
	return

def TestNeb(dig_ = "GauSH", net_ = "fc_sqdiff"):
	"""
	Test NudgedElasticBand
	"""
	tfm=TFManage("SmallMols_20rot_"+dig_+"_"+net_,None,False)
	optimizer  = Optimizer(tfm)
	a=MSet("NEB_Berg")
	a.ReadXYZ("NEB_Berg")
	m0 = a.mols[0]
	m1 = a.mols[1]
	# These have to be aligned and optimized if you want a good PES.
	m0.AlignAtoms(m1)
	m0 = optimizer.OptTFRealForce(m0,"NebOptM0")
	m1 = optimizer.OptTFRealForce(m1,"NebOptM1")
	PARAMS["NebNumBeads"] = 30
	PARAMS["NebK"] = 2.0
	PARAMS["OptStepSize"] = 0.002
	PARAMS["OptMomentum"] = 0.0
	PARAMS["OptMomentumDecay"] = 1.0
	neb = NudgedElasticBand(tfm, m0, m1)
	neb.OptNeb()
	return

def TestMetadynamics():
	a = MSet("nicotine_opt")
	# a.mols.append(Mol(np.array([1,1,8]),np.array([[0.9,0.1,0.1],[1.,0.9,1.],[0.1,0.1,0.1]])))
	a.ReadXYZ()
	m = a.mols[0]
	ForceField = lambda x: QchemDFT(Mol(m.atoms,x),basis_ = '6-311g**',xc_='wB97X-D', jobtype_='force', filename_='jmols2', path_='./qchem/', threads=8)
	masses = np.array(map(lambda x: ATOMICMASSESAMU[x-1],m.atoms))
	print "Masses:", masses
	PARAMS["MDdt"] = 0.02
	PARAMS["RemoveInvariant"]=True
	PARAMS["MDMaxStep"] = 100
	PARAMS["MDThermostat"] = "Nose"
	PARAMS["MDTemp"]= 300.0
	PARAMS["MDV0"] = "Thermal"
	meta = MetaDynamics(ForceField, m)
	meta.Prop()

def TestTFBond():
	a=MSet("chemspider_all_rand")
	a.Load()
	d = MolDigester(a.BondTypes(), name_="CZ", OType_="AtomizationEnergy")
	tset = TensorMolData_BPBond_Direct(a,d)
	manager=TFMolManage("",tset,True,"fc_sqdiff_BPBond_Direct")

def GetPairPotential():
	manager=TFMolManage("Mol_SmallMols_rand_CZ_fc_sqdiff_BPBond_Direct_1", Trainable_ = False)
	PairPotVals = manager.EvalBPPairPotential()
	for i in range(len(PairPotVals)):
		np.savetxt("PairPotentialValues_elempair_"+str(i)+".dat",PairPotVals[i])

def TestTFGauSH():
	tf_precision = eval(PARAMS["tf_prec"])
	TensorMol.RawEmbeddings.data_precision = tf_precision
	np.set_printoptions(threshold=100000)
	a=MSet("SmallMols_rand")
	a.Load()
	maxnatoms = a.MaxNAtoms()
	zlist = []
	xyzlist = []
	labelslist = []
	natomlist = []
	for i, mol in enumerate(a.mols):
		paddedxyz = np.zeros((maxnatoms,3), dtype=np.float32)
		paddedxyz[:mol.atoms.shape[0]] = mol.coords
		paddedz = np.zeros((maxnatoms), dtype=np.int32)
		paddedz[:mol.atoms.shape[0]] = mol.atoms
		paddedlabels = np.zeros((maxnatoms, 3), dtype=np.float32)
		paddedlabels[:mol.atoms.shape[0]] = mol.properties["forces"]
		xyzlist.append(paddedxyz)
		zlist.append(paddedz)
		labelslist.append(paddedlabels)
		natomlist.append(mol.NAtoms())
		if i == 999:
			break
	xyzstack = tf.stack(xyzlist)
	zstack = tf.stack(zlist)
	labelstack = tf.stack(labelslist)
	natomstack = tf.stack(natomlist)
	gaussian_params = tf.Variable(PARAMS["RBFS"], trainable=True, dtype=tf.float32)
	atomic_embed_factors = tf.Variable(PARAMS["ANES"], trainable=True, dtype=tf.float32)
	elements = tf.constant([1, 6, 7, 8], dtype=tf.int32)
	tmp = tf_gaussian_spherical_harmonics_channel(xyzstack, zstack, elements, gaussian_params, 4)
	sess = tf.Session()
	sess.run(tf.global_variables_initializer())
	options = tf.RunOptions(trace_level=tf.RunOptions.FULL_TRACE)
	run_metadata = tf.RunMetadata()
	# for i in range(a.mols[0].atoms.shape[0]):
	# 	print a.mols[0].atoms[i], "   ", a.mols[0].coords[i,0], "   ", a.mols[0].coords[i,1], "   ", a.mols[0].coords[i,2]
	tmp2 = sess.run(tmp, options=options, run_metadata=run_metadata)
	print tmp2
	# print tmp2[1]
	# print tmp2.shape
	# print tmp3
	fetched_timeline = timeline.Timeline(run_metadata.step_stats)
	chrome_trace = fetched_timeline.generate_chrome_trace_format()
	with open('timeline_step_tmp_tm_nocheck_h2o.json', 'w') as f:
		f.write(chrome_trace)
	# print tmp2[3].shape
	# print a.mols[0].atoms.shape
	# TreatedAtoms = a.AtomTypes()
	# d = Digester(TreatedAtoms, name_="GauSH", OType_="Force")
	# # tset = TensorData(a,d)
	# mol_ = a.mols[0]
	# print d.Emb(mol_, -1, mol_.coords[0], MakeOutputs=False)[0]
	# print mol_.atoms[0]

def test_gaussian_overlap():
	gaussian_params = tf.Variable(PARAMS["RBFS"], trainable=True, dtype=tf.float32)
	tf_precision = eval(PARAMS["tf_prec"])
	TensorMol.RawEmbeddings.data_precision = tf_precision
	tmp = tf_gaussian_overlap(gaussian_params)
	sess = tf.Session()
	sess.run(tf.global_variables_initializer())
	tmp2 = sess.run(tmp)
	print tmp2

def train_forces_GauSH_direct(set_ = "SmallMols"):
	PARAMS["RBFS"] = np.array([[0.35, 0.35], [0.70, 0.35], [1.05, 0.35], [1.40, 0.35], [1.75, 0.35], [2.10, 0.35], [2.45, 0.35],
								[2.80, 0.35], [3.15, 0.35], [3.50, 0.35], [3.85, 0.35], [4.20, 0.35], [4.55, 0.35], [4.90, 0.35]])
	PARAMS["ANES"] = np.array([2.20, 1.0, 1.0, 1.0, 1.0, 2.55, 3.04, 3.44]) #pauling electronegativity
	PARAMS["SH_NRAD"] = 14
	PARAMS["SH_LMAX"] = 4
	PARAMS["HiddenLayers"] = [512, 512, 512, 512, 512, 512, 512]
	PARAMS["max_steps"] = 20000
	PARAMS["test_freq"] = 5
	PARAMS["batch_size"] = 200
	PARAMS["NeuronType"] = "elu"
	PARAMS["learning_rate"] = 0.0001
	a=MSet(set_)
	a.Load()
	TreatedAtoms = a.AtomTypes()
	print "Number of Mols: ", len(a.mols)
	d = Digester(TreatedAtoms, name_="GauSH", OType_="Force")
	tset = TensorDataDirect(a,d)
	manager=TFManage("",tset,True,"fc_sqdiff_GauSH_direct")

def train_forces_rotation_constraint(set_ = "SmallMols"):
	PARAMS["RBFS"] = np.array([[0.35, 0.35], [0.70, 0.35], [1.05, 0.35], [1.40, 0.35], [1.75, 0.35], [2.10, 0.35], [2.45, 0.35],
								[2.80, 0.35], [3.15, 0.35], [3.50, 0.35], [3.85, 0.35], [4.20, 0.35], [4.55, 0.35], [4.90, 0.35]])
	PARAMS["ANES"] = np.array([2.20, 1.0, 1.0, 1.0, 1.0, 2.55, 3.04, 3.44]) #pauling electronegativity
	PARAMS["SH_NRAD"] = 14
	PARAMS["SH_LMAX"] = 4
	PARAMS["HiddenLayers"] = [512, 512, 512]
	PARAMS["max_steps"] = 1000
	PARAMS["test_freq"] = 5
	PARAMS["batch_size"] = 100
	PARAMS["NeuronType"] = "elu"
	PARAMS["learning_rate"] = 0.0001
	PARAMS["tf_prec"] = "tf.float32"
	a=MSet(set_)
	a.Load()
	TreatedAtoms = a.AtomTypes()
	print "Number of Mols: ", len(a.mols)
	d = Digester(TreatedAtoms, name_="GauSH", OType_="Force")
	tset = TensorDataDirect(a,d)
	manager=TFManage("",tset,False,"fc_sqdiff_GauSH_direct_constrain_rotation")
	manager.TrainElement(7)

def test_tf_neighbor():
	np.set_printoptions(threshold=100000)
	a=MSet("SmallMols_rand")
	a.Load()
	maxnatoms = a.MaxNAtoms()
	zlist = []
	xyzlist = []
	labelslist = []
	for i, mol in enumerate(a.mols):
		paddedxyz = np.zeros((maxnatoms,3), dtype=np.float32)
		paddedxyz[:mol.atoms.shape[0]] = mol.coords
		paddedz = np.zeros((maxnatoms), dtype=np.int32)
		paddedz[:mol.atoms.shape[0]] = mol.atoms
		paddedlabels = np.zeros((maxnatoms, 3), dtype=np.float32)
		paddedlabels[:mol.atoms.shape[0]] = mol.properties["forces"]
		xyzlist.append(paddedxyz)
		zlist.append(paddedz)
		labelslist.append(paddedlabels)
		if i == 99:
			break
	xyzstack = tf.stack(xyzlist)
	zstack = tf.stack(zlist)
	labelstack = tf.stack(labelslist)
	gaussian_params = tf.Variable(PARAMS["RBFS"], trainable=True, dtype=tf.float32)
	atomic_embed_factors = tf.Variable(PARAMS["ANES"], trainable=True, dtype=tf.float32)
	element = tf.constant(1, dtype=tf.int32)
	r_cutoff = tf.constant(5.0, dtype=tf.float32)
	element_pairs = tf.constant([[1,1,1], [1,1,6], [1,1,7], [1,1,8], [1,6,6], [1,6,7], [1,6,8], [1,7,7], [1,7,8], [1,8,8],
								[6,6,6], [6,6,7], [6,6,8], [6,7,7], [6,7,8], [6,8,8], [7,7,7], [7,7,8], [7,8,8], [8,8,8]], dtype=tf.int32)
	tmp = tf_triples_list(xyzstack, zstack, r_cutoff, element_pairs)
	sess = tf.Session()
	sess.run(tf.global_variables_initializer())
	options = tf.RunOptions(trace_level=tf.RunOptions.FULL_TRACE)
	run_metadata = tf.RunMetadata()
	# for i in range(a.mols[0].atoms.shape[0]):
	# 	print a.mols[0].atoms[i], "   ", a.mols[0].coords[i,0], "   ", a.mols[0].coords[i,1], "   ", a.mols[0].coords[i,2]
	tmp3 = sess.run([tmp], options=options, run_metadata=run_metadata)
	# print tmp3
	fetched_timeline = timeline.Timeline(run_metadata.step_stats)
	chrome_trace = fetched_timeline.generate_chrome_trace_format()
	with open('timeline_step_tmp_tm_nocheck_h2o.json', 'w') as f:
		f.write(chrome_trace)
	print tmp3
	# print tmp4[1]
	# print tmp4
	# TreatedAtoms = a.AtomTypes()
	# d = Digester(TreatedAtoms, name_="GauSH", OType_="Force")
	# # tset = TensorData(a,d)
	# mol_ = a.mols[0]
	# print d.Emb(mol_, -1, mol_.coords[0], MakeOutputs=False)[0]
	# print mol_.atoms[0]

def train_energy_pairs_triples():
	PARAMS["HiddenLayers"] = [512, 512, 512]
	PARAMS["learning_rate"] = 0.0001
	PARAMS["max_steps"] = 1000
	PARAMS["test_freq"] = 5
	PARAMS["batch_size"] = 200
	PARAMS["NeuronType"] = "relu"
	# PARAMS["tf_prec"] = "tf.float64"
	# PARAMS["self.profiling"] = True
	a=MSet("SmallMols")
	a.Load()
	TreatedAtoms = a.AtomTypes()
	print "Number of Mols: ", len(a.mols)
	d = Digester(TreatedAtoms, name_="GauSH", OType_="AtomizationEnergy")
	tset = TensorMolData_BP_Direct(a,d)
	manager=TFMolManage("",tset,True,"pairs_triples", Trainable_=True)

def train_energy_symm_func(mset):
	PARAMS["train_energy_gradients"] = False
	PARAMS["weight_decay"] = None
	PARAMS["HiddenLayers"] = [512, 512, 512]
	PARAMS["learning_rate"] = 0.0001
	PARAMS["max_steps"] = 500
	PARAMS["test_freq"] = 5
	PARAMS["batch_size"] = 200
	PARAMS["NeuronType"] = "elu"
	PARAMS["tf_prec"] = "tf.float32"
	a=MSet(mset)
	a.Load()
	print "Number of Mols: ", len(a.mols)
	manager = TFMolManageDirect(a, network_type = "BehlerParinelloDirectSymFunc")

def train_energy_GauSH():
	PARAMS["RBFS"] = np.stack((np.linspace(0.1, 5.0, 14), np.repeat(0.35, 14)), axis=1)
	PARAMS["SH_NRAD"] = 14
	PARAMS["SH_LMAX"] = 4
	PARAMS["EECutoffOn"] = 0.0
	PARAMS["Elu_Width"] = 4.5
	PARAMS["train_energy_gradients"] = True
	PARAMS["weight_decay"] = None
	PARAMS["HiddenLayers"] = [512, 512, 512]
	PARAMS["learning_rate"] = 0.0001
	PARAMS["max_steps"] = 250
	PARAMS["test_freq"] = 5
	PARAMS["batch_size"] = 400
	PARAMS["NeuronType"] = "elu"
	PARAMS["tf_prec"] = "tf.float32"
	PARAMS["Profiling"] = False
	a=MSet("H2O_wb97xd_1to21_with_prontonated")
	a.Load()
	manager = TFMolManageDirect(a, network_type = "BehlerParinelloDirectGauSH")

def geo_opt_tf_forces(mset, manager_name, mol_index):
	PARAMS["RBFS"] = np.array([[0.35, 0.35], [0.70, 0.35], [1.05, 0.35], [1.40, 0.35], [1.75, 0.35], [2.10, 0.35], [2.45, 0.35],
								[2.80, 0.35], [3.15, 0.35], [3.50, 0.35], [3.85, 0.35], [4.20, 0.35], [4.55, 0.35], [4.90, 0.35]])
	PARAMS["ANES"] = np.array([2.20, 1.0, 1.0, 1.0, 1.0, 2.55, 3.04, 3.44]) #pauling electronegativity
	PARAMS["SH_NRAD"] = 14
	PARAMS["SH_LMAX"] = 4
	PARAMS["OptMaxCycles"]=50000
	PARAMS["OptStepSize"] = 0.1
	PARAMS["OptThresh"]=0.0001
	a=MSet(mset)
	a.ReadXYZ()
	mol=a.mols[mol_index]
	manager=TFManage(Name_=manager_name,Train_=False,NetType_="fc_sqdiff_GauSH_direct")
	# print manager.evaluate_mol_forces_direct(mol)
	# print mol.properties["forces"]
	force_field = lambda x: manager.evaluate_mol_forces_direct(x)
	Opt = GeomOptimizer(force_field)
	Opt.Opt_GD_forces_only(mol)

def test_md():
	PARAMS["RBFS"] = np.array([[0.35, 0.35], [0.70, 0.35], [1.05, 0.35], [1.40, 0.35], [1.75, 0.35], [2.10, 0.35], [2.45, 0.35],
								[2.80, 0.35], [3.15, 0.35], [3.50, 0.35], [3.85, 0.35], [4.20, 0.35], [4.55, 0.35], [4.90, 0.35]])
	PARAMS["ANES"] = np.array([2.20, 1.0, 1.0, 1.0, 1.0, 2.55, 3.04, 3.44]) #pauling electronegativity
	PARAMS["SH_NRAD"] = 14
	PARAMS["SH_LMAX"] = 4
	a = MSet("OptMols")
	a.ReadXYZ()
	mol = a.mols[4]
	manager=TFManage(Name_="SmallMols_GauSH_fc_sqdiff_GauSH_direct",Train_=False,NetType_="fc_sqdiff_GauSH_direct")
	force_field = lambda x: manager.evaluate_mol_forces_direct(x)
	masses = np.array(map(lambda x: ATOMICMASSESAMU[x-1], mol.atoms))
	print "Masses:", masses
	PARAMS["MDdt"] = 0.2
	PARAMS["RemoveInvariant"]=True
	PARAMS["MDMaxStep"] = 20000
	PARAMS["MDThermostat"] = "Nose"
	PARAMS["MDTemp"]= 300.0
	md = VelocityVerlet(force_field, mol)
	md.Prop()

def test_h2o():
	PARAMS["OptMaxCycles"]=60
	PARAMS["OptMaxCycles"]=500
	PARAMS["OptStepSize"] = 0.1
	PARAMS["OptThresh"]=0.0001
	PARAMS["MDAnnealT0"] = 20.0
	PARAMS["MDAnnealSteps"] = 2000
	a = MSet("water")
	# a.ReadXYZ()
	a.mols.append(Mol(np.array([1,1,8]),np.array([[0.9,0.1,0.1],[1.,0.9,1.],[0.1,0.1,0.1]])))
	mol = a.mols[0]
	manager = TFMolManageDirect(name="BehlerParinelloDirectGauSH_H2O_wb97xd_1to21_with_prontonated_Mon_Nov_13_11.11.15_2017", network_type = "BehlerParinelloDirectGauSH")
	def force_field(mol, eval_forces=True):
		if eval_forces:
			energy, forces = manager.evaluate_mol(mol, True)
			forces = RemoveInvariantForce(mol.coords, forces, mol.atoms)
			return energy, forces
		else:
			energy = manager.evaluate_mol(mol, False)
			return energy
	Opt = GeometryOptimizer(force_field)
	opt_mol = Opt.opt_conjugate_gradient(mol)

def test_h2o_anneal():
	PARAMS["OptMaxCycles"]=60
	PARAMS["OptMaxCycles"]=500
	PARAMS["OptStepSize"] = 0.1
	PARAMS["OptThresh"]=0.0001
	PARAMS["MDAnnealT0"] = 20.0
	PARAMS["MDAnnealSteps"] = 2000
	a = MSet()
	a.mols.append(Mol(np.array([1,1,8]),np.array([[0.9,0.1,0.1],[1.,0.9,1.],[0.1,0.1,0.1]])))
	mol = a.mols[0]
	manager = TFMolManageDirect(name="BehlerParinelloDirectGauSH_H2O_wb97xd_1to21_with_prontonated_Wed_Nov_01_16.53.25_2017", network_type = "BehlerParinelloDirectGauSH")
	def force_field(mol, eval_forces=True):
		if eval_forces:
			energy, forces = manager.evaluate(mol, True)
			forces = RemoveInvariantForce(mol.coords, forces, mol.atoms)
			return energy, forces
		else:
			energy = manager.evaluate(mol, False)
			return energy
	Opt = GeometryOptimizer(force_field)
	opt_mol = Opt.opt_conjugate_gradient(mol)

	# Tesselate that water to create a box
	ntess = 4
	latv = 2.8*np.eye(3)
	# Start with a water in a ten angstrom box.
	lat = Lattice(latv)
	mc = lat.CenteredInLattice(opt_mol)
	mt = Mol(*lat.TessNTimes(mc.atoms,mc.coords,ntess))
	nreal = mt.NAtoms()
	mt.Distort(0.01)
	annealer = AnnealerDirect(force_field)
	annealer.propagate(mt)
	# mt.coords = aper.Minx

def evaluate_BPSymFunc(mset):
	a=MSet(mset)
	a.Load()
	output, labels = [], []
	manager = TFMolManageDirect(name="BehlerParinelloDirectSymFunc_nicotine_aimd_40000_Fri_Nov_10_17.36.01_2017", network_type = "BehlerParinelloDirectSymFunc")
	random.shuffle(a.mols)
	batch = []
	for i in range(len(a.mols) / 100):
		for j in range(100):
			labels.append(a.mols[i*100+j].properties["atomization"])
			batch.append(a.mols[i*100+j])
		output.append(manager.evaluate_batch(batch, eval_forces=False))
		batch = []
	output = np.concatenate(output)
	labels = np.array(labels)
	print "MAE:", np.mean(np.abs(output-labels))*627.509
	print "RMSE:",np.sqrt(np.mean(np.square(output-labels)))*627.509

def water_dimer_plot():
	PARAMS["RBFS"] = np.stack((np.linspace(0.1, 5.0, 32), np.repeat(0.25, 32)), axis=1)
	PARAMS["SH_NRAD"] = 32
	PARAMS["SH_LMAX"] = 4
	def qchemdft(m_,ghostatoms,basis_ = '6-31g*',xc_='b3lyp', jobtype_='force', filename_='tmp', path_='./qchem/', threads=False):
		istring = '$molecule\n0 1 \n'
		crds = m_.coords.copy()
		crds[abs(crds)<0.0000] *=0.0
		for j in range(len(m_.atoms)):
			if j in ghostatoms:
				istring=istring+"@"+itoa[m_.atoms[j]]+' '+str(crds[j,0])+' '+str(crds[j,1])+' '+str(crds[j,2])+'\n'
			else:
				istring=istring+itoa[m_.atoms[j]]+' '+str(crds[j,0])+' '+str(crds[j,1])+' '+str(crds[j,2])+'\n'
		if jobtype_ == "dipole":
			istring =istring + '$end\n\n$rem\njobtype sp\nbasis '+basis_+'\nmethod '+xc_+'\nthresh 11\nsymmetry false\nsym_ignore true\n$end\n'
		else:
			istring =istring + '$end\n\n$rem\njobtype '+jobtype_+'\nbasis '+basis_+'\nmethod '+xc_+'\nthresh 11\nsymmetry false\nsym_ignore true\n$end\n'
		with open(path_+filename_+'.in','w') as fin:
			fin.write(istring)
		with open(path_+filename_+'.out','a') as fout:
			if threads:
				proc = subprocess.Popen(['qchem', '-nt', str(threads), path_+filename_+'.in'], stdout=subprocess.PIPE, stderr=subprocess.PIPE,shell=False)
			else:
				proc = subprocess.Popen(['qchem', path_+filename_+'.in'], stdout=subprocess.PIPE, stderr=subprocess.PIPE,shell=False)
			out, err = proc.communicate()
			fout.write(out)
		lines = out.split('\n')
		if jobtype_ == 'force':
			Forces = np.zeros((m_.atoms.shape[0],3))
			for i, line in enumerate(lines):
				if line.count('Convergence criterion met')>0:
					Energy = float(line.split()[1])
				if line.count("Gradient of SCF Energy") > 0:
					k = 0
					l = 0
					for j in range(1, m_.atoms.shape[0]+1):
						Forces[j-1,:] = float(lines[i+k+2].split()[l+1]), float(lines[i+k+3].split()[l+1]), float(lines[i+k+4].split()[l+1])
						l += 1
						if (j % 6) == 0:
							k += 4
							l = 0
			# return Energy, Forces
			return Energy, -Forces*JOULEPERHARTREE/BOHRPERA
		elif jobtype_ == 'sp':
			for line in lines:
				if line.count('Convergence criterion met')>0:
					Energy = float(line.split()[1])
			return Energy
		else:
			raise Exception("jobtype needs formatted for return variables")

	a = MSet("water_dimer")
	a.ReadXYZ()
	manager = TFMolManageDirect(name="BehlerParinelloDirectGauSH_H2O_wb97xd_1to21_with_prontonated_Mon_Nov_13_11.35.07_2017", network_type = "BehlerParinelloDirectGauSH")
	qchemff = lambda x, y: qchemdft(x, y, basis_ = '6-311g**',xc_='wb97x-d', jobtype_='sp', filename_='tmp', path_='./qchem/', threads=8)
	cp_correction = []
	for mol in a.mols:
		h2o1 = qchemff(Mol(mol.atoms[:3], mol.coords[:3]), [])
		h2o2 = qchemff(Mol(mol.atoms[3:], mol.coords[3:]), [])
		# h2o1cp = qchemff(mol, [3, 4, 5])
		# h2o2cp = qchemff(mol, [0, 1, 2])
		dimer = qchemff(mol, [])
		# cpc = h2o1cp - h2o1 + h2o2cp - h2o2
		# cp_correction.append(cpc)
		bond_e = dimer - h2o1 - h2o2
		print "{%.10f, %.10f}," % (np.linalg.norm(mol.coords[1] - mol.coords[3]), bond_e * 627.509)
	print "TensorMol evaluation"
	for i, mol in enumerate(a.mols):
		h2o1 = manager.evaluate_mol(Mol(mol.atoms[:3], mol.coords[:3]), False)
		h2o2 = manager.evaluate_mol(Mol(mol.atoms[3:], mol.coords[3:]), False)
		dimer = manager.evaluate_mol(mol, False)
		bond_e = dimer - h2o1 - h2o2
		print "{%.10f, %.10f}," % (np.linalg.norm(mol.coords[1] - mol.coords[3]), bond_e * 627.509)

# PARAMS["RBFS"] = np.stack((np.linspace(0.1, 5.0, 32), np.repeat(0.25, 32)), axis=1)
# PARAMS["SH_NRAD"] = 32
# PARAMS["SH_LMAX"] = 4
# a = MSet("water_dimer")
# a.ReadXYZ()
# manager = TFMolManageDirect(name="BehlerParinelloDirectGauSH_H2O_wb97xd_1to21_with_prontonated_Mon_Nov_13_11.35.07_2017", network_type = "BehlerParinelloDirectGauSH")
# print manager.evaluate_mol(a.mols[0], False).shape
# for i in range(100):
# 	mol = Mol(a.mols[0].atoms, rot_coords[0,i])
#  	mol.WriteXYZfile()

# InterpoleGeometries()
# ReadSmallMols(set_="SmallMols", forces=True, energy=True)
# ReadSmallMols(set_="chemspider3", dir_="/media/sdb2/jeherr/TensorMol/datasets/chemspider3_data/*/", energy=True, forces=True)
# TrainKRR(set_="SmallMols_rand", dig_ = "GauSH", OType_="Force")
# RandomSmallSet("SmallMols", 10000)
# BasisOpt_KRR("KRR", "SmallMols_rand", "GauSH", OType = "Force", Elements_ = [1,6,7,8])
# BasisOpt_Ipecac("KRR", "ammonia_rand", "GauSH")
# TestIpecac()
# TestOCSDB()
# BIMNN_NEq()
# TestMetadynamics()
# TestMD()
# TestTFBond()
# GetPairPotential()
# TestTFGauSH()
# train_forces_GauSH_direct("SmallMols_rand")
# TestTFSym()
# train_energy_symm_func_channel()
# test_gaussian_overlap()
# train_forces_rotation_constraint("SmallMols")
# read_unpacked_set()
# test_tf_neighbor()
# train_energy_pairs_triples()
# train_energy_symm_func("nicotine_full")
train_energy_GauSH()
# geo_opt_tf_forces("dialanine", "SmallMols_GauSH_fc_sqdiff_GauSH_direct", 0)
# test_md()
# test_h2o()
# test_h2o_anneal()
# evaluate_BPSymFunc("nicotine_aimd")
# water_dimer_plot()

# a=MSet("water_dimer_cccbdb_opt")
# a.ReadXYZ()
# b = MSet("water_dimer")
# mol = a.mols[0]
# oovec = mol.coords[1] - mol.coords[3]
# for i in range(-80, 30):
# 	coords = mol.coords.copy()
# 	coords[3:] += 0.01 * i * oovec
# 	new_mol = Mol(mol.atoms, coords)
# 	b.mols.append(new_mol)
# 	print np.linalg.norm(b.mols[-1].coords[1] - b.mols[-1].coords[3])
# b.WriteXYZ()
