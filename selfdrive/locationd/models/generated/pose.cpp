#include "pose.h"

namespace {
#define DIM 18
#define EDIM 18
#define MEDIM 18
typedef void (*Hfun)(double *, double *, double *);
const static double MAHA_THRESH_4 = 7.814727903251177;
const static double MAHA_THRESH_10 = 7.814727903251177;
const static double MAHA_THRESH_13 = 7.814727903251177;
const static double MAHA_THRESH_14 = 7.814727903251177;

/******************************************************************************
 *                      Code generated with SymPy 1.14.0                      *
 *                                                                            *
 *              See http://www.sympy.org/ for more information.               *
 *                                                                            *
 *                         This file is part of 'ekf'                         *
 ******************************************************************************/
void err_fun(double *nom_x, double *delta_x, double *out_1302557212303107234) {
   out_1302557212303107234[0] = delta_x[0] + nom_x[0];
   out_1302557212303107234[1] = delta_x[1] + nom_x[1];
   out_1302557212303107234[2] = delta_x[2] + nom_x[2];
   out_1302557212303107234[3] = delta_x[3] + nom_x[3];
   out_1302557212303107234[4] = delta_x[4] + nom_x[4];
   out_1302557212303107234[5] = delta_x[5] + nom_x[5];
   out_1302557212303107234[6] = delta_x[6] + nom_x[6];
   out_1302557212303107234[7] = delta_x[7] + nom_x[7];
   out_1302557212303107234[8] = delta_x[8] + nom_x[8];
   out_1302557212303107234[9] = delta_x[9] + nom_x[9];
   out_1302557212303107234[10] = delta_x[10] + nom_x[10];
   out_1302557212303107234[11] = delta_x[11] + nom_x[11];
   out_1302557212303107234[12] = delta_x[12] + nom_x[12];
   out_1302557212303107234[13] = delta_x[13] + nom_x[13];
   out_1302557212303107234[14] = delta_x[14] + nom_x[14];
   out_1302557212303107234[15] = delta_x[15] + nom_x[15];
   out_1302557212303107234[16] = delta_x[16] + nom_x[16];
   out_1302557212303107234[17] = delta_x[17] + nom_x[17];
}
void inv_err_fun(double *nom_x, double *true_x, double *out_645935160919976454) {
   out_645935160919976454[0] = -nom_x[0] + true_x[0];
   out_645935160919976454[1] = -nom_x[1] + true_x[1];
   out_645935160919976454[2] = -nom_x[2] + true_x[2];
   out_645935160919976454[3] = -nom_x[3] + true_x[3];
   out_645935160919976454[4] = -nom_x[4] + true_x[4];
   out_645935160919976454[5] = -nom_x[5] + true_x[5];
   out_645935160919976454[6] = -nom_x[6] + true_x[6];
   out_645935160919976454[7] = -nom_x[7] + true_x[7];
   out_645935160919976454[8] = -nom_x[8] + true_x[8];
   out_645935160919976454[9] = -nom_x[9] + true_x[9];
   out_645935160919976454[10] = -nom_x[10] + true_x[10];
   out_645935160919976454[11] = -nom_x[11] + true_x[11];
   out_645935160919976454[12] = -nom_x[12] + true_x[12];
   out_645935160919976454[13] = -nom_x[13] + true_x[13];
   out_645935160919976454[14] = -nom_x[14] + true_x[14];
   out_645935160919976454[15] = -nom_x[15] + true_x[15];
   out_645935160919976454[16] = -nom_x[16] + true_x[16];
   out_645935160919976454[17] = -nom_x[17] + true_x[17];
}
void H_mod_fun(double *state, double *out_3435950681424489829) {
   out_3435950681424489829[0] = 1.0;
   out_3435950681424489829[1] = 0.0;
   out_3435950681424489829[2] = 0.0;
   out_3435950681424489829[3] = 0.0;
   out_3435950681424489829[4] = 0.0;
   out_3435950681424489829[5] = 0.0;
   out_3435950681424489829[6] = 0.0;
   out_3435950681424489829[7] = 0.0;
   out_3435950681424489829[8] = 0.0;
   out_3435950681424489829[9] = 0.0;
   out_3435950681424489829[10] = 0.0;
   out_3435950681424489829[11] = 0.0;
   out_3435950681424489829[12] = 0.0;
   out_3435950681424489829[13] = 0.0;
   out_3435950681424489829[14] = 0.0;
   out_3435950681424489829[15] = 0.0;
   out_3435950681424489829[16] = 0.0;
   out_3435950681424489829[17] = 0.0;
   out_3435950681424489829[18] = 0.0;
   out_3435950681424489829[19] = 1.0;
   out_3435950681424489829[20] = 0.0;
   out_3435950681424489829[21] = 0.0;
   out_3435950681424489829[22] = 0.0;
   out_3435950681424489829[23] = 0.0;
   out_3435950681424489829[24] = 0.0;
   out_3435950681424489829[25] = 0.0;
   out_3435950681424489829[26] = 0.0;
   out_3435950681424489829[27] = 0.0;
   out_3435950681424489829[28] = 0.0;
   out_3435950681424489829[29] = 0.0;
   out_3435950681424489829[30] = 0.0;
   out_3435950681424489829[31] = 0.0;
   out_3435950681424489829[32] = 0.0;
   out_3435950681424489829[33] = 0.0;
   out_3435950681424489829[34] = 0.0;
   out_3435950681424489829[35] = 0.0;
   out_3435950681424489829[36] = 0.0;
   out_3435950681424489829[37] = 0.0;
   out_3435950681424489829[38] = 1.0;
   out_3435950681424489829[39] = 0.0;
   out_3435950681424489829[40] = 0.0;
   out_3435950681424489829[41] = 0.0;
   out_3435950681424489829[42] = 0.0;
   out_3435950681424489829[43] = 0.0;
   out_3435950681424489829[44] = 0.0;
   out_3435950681424489829[45] = 0.0;
   out_3435950681424489829[46] = 0.0;
   out_3435950681424489829[47] = 0.0;
   out_3435950681424489829[48] = 0.0;
   out_3435950681424489829[49] = 0.0;
   out_3435950681424489829[50] = 0.0;
   out_3435950681424489829[51] = 0.0;
   out_3435950681424489829[52] = 0.0;
   out_3435950681424489829[53] = 0.0;
   out_3435950681424489829[54] = 0.0;
   out_3435950681424489829[55] = 0.0;
   out_3435950681424489829[56] = 0.0;
   out_3435950681424489829[57] = 1.0;
   out_3435950681424489829[58] = 0.0;
   out_3435950681424489829[59] = 0.0;
   out_3435950681424489829[60] = 0.0;
   out_3435950681424489829[61] = 0.0;
   out_3435950681424489829[62] = 0.0;
   out_3435950681424489829[63] = 0.0;
   out_3435950681424489829[64] = 0.0;
   out_3435950681424489829[65] = 0.0;
   out_3435950681424489829[66] = 0.0;
   out_3435950681424489829[67] = 0.0;
   out_3435950681424489829[68] = 0.0;
   out_3435950681424489829[69] = 0.0;
   out_3435950681424489829[70] = 0.0;
   out_3435950681424489829[71] = 0.0;
   out_3435950681424489829[72] = 0.0;
   out_3435950681424489829[73] = 0.0;
   out_3435950681424489829[74] = 0.0;
   out_3435950681424489829[75] = 0.0;
   out_3435950681424489829[76] = 1.0;
   out_3435950681424489829[77] = 0.0;
   out_3435950681424489829[78] = 0.0;
   out_3435950681424489829[79] = 0.0;
   out_3435950681424489829[80] = 0.0;
   out_3435950681424489829[81] = 0.0;
   out_3435950681424489829[82] = 0.0;
   out_3435950681424489829[83] = 0.0;
   out_3435950681424489829[84] = 0.0;
   out_3435950681424489829[85] = 0.0;
   out_3435950681424489829[86] = 0.0;
   out_3435950681424489829[87] = 0.0;
   out_3435950681424489829[88] = 0.0;
   out_3435950681424489829[89] = 0.0;
   out_3435950681424489829[90] = 0.0;
   out_3435950681424489829[91] = 0.0;
   out_3435950681424489829[92] = 0.0;
   out_3435950681424489829[93] = 0.0;
   out_3435950681424489829[94] = 0.0;
   out_3435950681424489829[95] = 1.0;
   out_3435950681424489829[96] = 0.0;
   out_3435950681424489829[97] = 0.0;
   out_3435950681424489829[98] = 0.0;
   out_3435950681424489829[99] = 0.0;
   out_3435950681424489829[100] = 0.0;
   out_3435950681424489829[101] = 0.0;
   out_3435950681424489829[102] = 0.0;
   out_3435950681424489829[103] = 0.0;
   out_3435950681424489829[104] = 0.0;
   out_3435950681424489829[105] = 0.0;
   out_3435950681424489829[106] = 0.0;
   out_3435950681424489829[107] = 0.0;
   out_3435950681424489829[108] = 0.0;
   out_3435950681424489829[109] = 0.0;
   out_3435950681424489829[110] = 0.0;
   out_3435950681424489829[111] = 0.0;
   out_3435950681424489829[112] = 0.0;
   out_3435950681424489829[113] = 0.0;
   out_3435950681424489829[114] = 1.0;
   out_3435950681424489829[115] = 0.0;
   out_3435950681424489829[116] = 0.0;
   out_3435950681424489829[117] = 0.0;
   out_3435950681424489829[118] = 0.0;
   out_3435950681424489829[119] = 0.0;
   out_3435950681424489829[120] = 0.0;
   out_3435950681424489829[121] = 0.0;
   out_3435950681424489829[122] = 0.0;
   out_3435950681424489829[123] = 0.0;
   out_3435950681424489829[124] = 0.0;
   out_3435950681424489829[125] = 0.0;
   out_3435950681424489829[126] = 0.0;
   out_3435950681424489829[127] = 0.0;
   out_3435950681424489829[128] = 0.0;
   out_3435950681424489829[129] = 0.0;
   out_3435950681424489829[130] = 0.0;
   out_3435950681424489829[131] = 0.0;
   out_3435950681424489829[132] = 0.0;
   out_3435950681424489829[133] = 1.0;
   out_3435950681424489829[134] = 0.0;
   out_3435950681424489829[135] = 0.0;
   out_3435950681424489829[136] = 0.0;
   out_3435950681424489829[137] = 0.0;
   out_3435950681424489829[138] = 0.0;
   out_3435950681424489829[139] = 0.0;
   out_3435950681424489829[140] = 0.0;
   out_3435950681424489829[141] = 0.0;
   out_3435950681424489829[142] = 0.0;
   out_3435950681424489829[143] = 0.0;
   out_3435950681424489829[144] = 0.0;
   out_3435950681424489829[145] = 0.0;
   out_3435950681424489829[146] = 0.0;
   out_3435950681424489829[147] = 0.0;
   out_3435950681424489829[148] = 0.0;
   out_3435950681424489829[149] = 0.0;
   out_3435950681424489829[150] = 0.0;
   out_3435950681424489829[151] = 0.0;
   out_3435950681424489829[152] = 1.0;
   out_3435950681424489829[153] = 0.0;
   out_3435950681424489829[154] = 0.0;
   out_3435950681424489829[155] = 0.0;
   out_3435950681424489829[156] = 0.0;
   out_3435950681424489829[157] = 0.0;
   out_3435950681424489829[158] = 0.0;
   out_3435950681424489829[159] = 0.0;
   out_3435950681424489829[160] = 0.0;
   out_3435950681424489829[161] = 0.0;
   out_3435950681424489829[162] = 0.0;
   out_3435950681424489829[163] = 0.0;
   out_3435950681424489829[164] = 0.0;
   out_3435950681424489829[165] = 0.0;
   out_3435950681424489829[166] = 0.0;
   out_3435950681424489829[167] = 0.0;
   out_3435950681424489829[168] = 0.0;
   out_3435950681424489829[169] = 0.0;
   out_3435950681424489829[170] = 0.0;
   out_3435950681424489829[171] = 1.0;
   out_3435950681424489829[172] = 0.0;
   out_3435950681424489829[173] = 0.0;
   out_3435950681424489829[174] = 0.0;
   out_3435950681424489829[175] = 0.0;
   out_3435950681424489829[176] = 0.0;
   out_3435950681424489829[177] = 0.0;
   out_3435950681424489829[178] = 0.0;
   out_3435950681424489829[179] = 0.0;
   out_3435950681424489829[180] = 0.0;
   out_3435950681424489829[181] = 0.0;
   out_3435950681424489829[182] = 0.0;
   out_3435950681424489829[183] = 0.0;
   out_3435950681424489829[184] = 0.0;
   out_3435950681424489829[185] = 0.0;
   out_3435950681424489829[186] = 0.0;
   out_3435950681424489829[187] = 0.0;
   out_3435950681424489829[188] = 0.0;
   out_3435950681424489829[189] = 0.0;
   out_3435950681424489829[190] = 1.0;
   out_3435950681424489829[191] = 0.0;
   out_3435950681424489829[192] = 0.0;
   out_3435950681424489829[193] = 0.0;
   out_3435950681424489829[194] = 0.0;
   out_3435950681424489829[195] = 0.0;
   out_3435950681424489829[196] = 0.0;
   out_3435950681424489829[197] = 0.0;
   out_3435950681424489829[198] = 0.0;
   out_3435950681424489829[199] = 0.0;
   out_3435950681424489829[200] = 0.0;
   out_3435950681424489829[201] = 0.0;
   out_3435950681424489829[202] = 0.0;
   out_3435950681424489829[203] = 0.0;
   out_3435950681424489829[204] = 0.0;
   out_3435950681424489829[205] = 0.0;
   out_3435950681424489829[206] = 0.0;
   out_3435950681424489829[207] = 0.0;
   out_3435950681424489829[208] = 0.0;
   out_3435950681424489829[209] = 1.0;
   out_3435950681424489829[210] = 0.0;
   out_3435950681424489829[211] = 0.0;
   out_3435950681424489829[212] = 0.0;
   out_3435950681424489829[213] = 0.0;
   out_3435950681424489829[214] = 0.0;
   out_3435950681424489829[215] = 0.0;
   out_3435950681424489829[216] = 0.0;
   out_3435950681424489829[217] = 0.0;
   out_3435950681424489829[218] = 0.0;
   out_3435950681424489829[219] = 0.0;
   out_3435950681424489829[220] = 0.0;
   out_3435950681424489829[221] = 0.0;
   out_3435950681424489829[222] = 0.0;
   out_3435950681424489829[223] = 0.0;
   out_3435950681424489829[224] = 0.0;
   out_3435950681424489829[225] = 0.0;
   out_3435950681424489829[226] = 0.0;
   out_3435950681424489829[227] = 0.0;
   out_3435950681424489829[228] = 1.0;
   out_3435950681424489829[229] = 0.0;
   out_3435950681424489829[230] = 0.0;
   out_3435950681424489829[231] = 0.0;
   out_3435950681424489829[232] = 0.0;
   out_3435950681424489829[233] = 0.0;
   out_3435950681424489829[234] = 0.0;
   out_3435950681424489829[235] = 0.0;
   out_3435950681424489829[236] = 0.0;
   out_3435950681424489829[237] = 0.0;
   out_3435950681424489829[238] = 0.0;
   out_3435950681424489829[239] = 0.0;
   out_3435950681424489829[240] = 0.0;
   out_3435950681424489829[241] = 0.0;
   out_3435950681424489829[242] = 0.0;
   out_3435950681424489829[243] = 0.0;
   out_3435950681424489829[244] = 0.0;
   out_3435950681424489829[245] = 0.0;
   out_3435950681424489829[246] = 0.0;
   out_3435950681424489829[247] = 1.0;
   out_3435950681424489829[248] = 0.0;
   out_3435950681424489829[249] = 0.0;
   out_3435950681424489829[250] = 0.0;
   out_3435950681424489829[251] = 0.0;
   out_3435950681424489829[252] = 0.0;
   out_3435950681424489829[253] = 0.0;
   out_3435950681424489829[254] = 0.0;
   out_3435950681424489829[255] = 0.0;
   out_3435950681424489829[256] = 0.0;
   out_3435950681424489829[257] = 0.0;
   out_3435950681424489829[258] = 0.0;
   out_3435950681424489829[259] = 0.0;
   out_3435950681424489829[260] = 0.0;
   out_3435950681424489829[261] = 0.0;
   out_3435950681424489829[262] = 0.0;
   out_3435950681424489829[263] = 0.0;
   out_3435950681424489829[264] = 0.0;
   out_3435950681424489829[265] = 0.0;
   out_3435950681424489829[266] = 1.0;
   out_3435950681424489829[267] = 0.0;
   out_3435950681424489829[268] = 0.0;
   out_3435950681424489829[269] = 0.0;
   out_3435950681424489829[270] = 0.0;
   out_3435950681424489829[271] = 0.0;
   out_3435950681424489829[272] = 0.0;
   out_3435950681424489829[273] = 0.0;
   out_3435950681424489829[274] = 0.0;
   out_3435950681424489829[275] = 0.0;
   out_3435950681424489829[276] = 0.0;
   out_3435950681424489829[277] = 0.0;
   out_3435950681424489829[278] = 0.0;
   out_3435950681424489829[279] = 0.0;
   out_3435950681424489829[280] = 0.0;
   out_3435950681424489829[281] = 0.0;
   out_3435950681424489829[282] = 0.0;
   out_3435950681424489829[283] = 0.0;
   out_3435950681424489829[284] = 0.0;
   out_3435950681424489829[285] = 1.0;
   out_3435950681424489829[286] = 0.0;
   out_3435950681424489829[287] = 0.0;
   out_3435950681424489829[288] = 0.0;
   out_3435950681424489829[289] = 0.0;
   out_3435950681424489829[290] = 0.0;
   out_3435950681424489829[291] = 0.0;
   out_3435950681424489829[292] = 0.0;
   out_3435950681424489829[293] = 0.0;
   out_3435950681424489829[294] = 0.0;
   out_3435950681424489829[295] = 0.0;
   out_3435950681424489829[296] = 0.0;
   out_3435950681424489829[297] = 0.0;
   out_3435950681424489829[298] = 0.0;
   out_3435950681424489829[299] = 0.0;
   out_3435950681424489829[300] = 0.0;
   out_3435950681424489829[301] = 0.0;
   out_3435950681424489829[302] = 0.0;
   out_3435950681424489829[303] = 0.0;
   out_3435950681424489829[304] = 1.0;
   out_3435950681424489829[305] = 0.0;
   out_3435950681424489829[306] = 0.0;
   out_3435950681424489829[307] = 0.0;
   out_3435950681424489829[308] = 0.0;
   out_3435950681424489829[309] = 0.0;
   out_3435950681424489829[310] = 0.0;
   out_3435950681424489829[311] = 0.0;
   out_3435950681424489829[312] = 0.0;
   out_3435950681424489829[313] = 0.0;
   out_3435950681424489829[314] = 0.0;
   out_3435950681424489829[315] = 0.0;
   out_3435950681424489829[316] = 0.0;
   out_3435950681424489829[317] = 0.0;
   out_3435950681424489829[318] = 0.0;
   out_3435950681424489829[319] = 0.0;
   out_3435950681424489829[320] = 0.0;
   out_3435950681424489829[321] = 0.0;
   out_3435950681424489829[322] = 0.0;
   out_3435950681424489829[323] = 1.0;
}
void f_fun(double *state, double dt, double *out_5840201724917908869) {
   out_5840201724917908869[0] = atan2((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), -(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]));
   out_5840201724917908869[1] = asin(sin(dt*state[7])*cos(state[0])*cos(state[1]) - sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1]) + sin(state[1])*cos(dt*state[7])*cos(dt*state[8]));
   out_5840201724917908869[2] = atan2(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), -(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]));
   out_5840201724917908869[3] = dt*state[12] + state[3];
   out_5840201724917908869[4] = dt*state[13] + state[4];
   out_5840201724917908869[5] = dt*state[14] + state[5];
   out_5840201724917908869[6] = state[6];
   out_5840201724917908869[7] = state[7];
   out_5840201724917908869[8] = state[8];
   out_5840201724917908869[9] = state[9];
   out_5840201724917908869[10] = state[10];
   out_5840201724917908869[11] = state[11];
   out_5840201724917908869[12] = state[12];
   out_5840201724917908869[13] = state[13];
   out_5840201724917908869[14] = state[14];
   out_5840201724917908869[15] = state[15];
   out_5840201724917908869[16] = state[16];
   out_5840201724917908869[17] = state[17];
}
void F_fun(double *state, double dt, double *out_2069028585121272448) {
   out_2069028585121272448[0] = ((-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*cos(state[0])*cos(state[1]) - sin(state[0])*cos(dt*state[6])*cos(dt*state[7])*cos(state[1]))*(-(sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) - sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2)) + ((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*cos(state[0])*cos(state[1]) - sin(dt*state[6])*sin(state[0])*cos(dt*state[7])*cos(state[1]))*(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2));
   out_2069028585121272448[1] = ((-sin(dt*state[6])*sin(dt*state[8]) - sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*cos(state[1]) - (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*sin(state[1]) - sin(state[1])*cos(dt*state[6])*cos(dt*state[7])*cos(state[0]))*(-(sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) - sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2)) + (-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))*(-(sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*sin(state[1]) + (-sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) + sin(dt*state[8])*cos(dt*state[6]))*cos(state[1]) - sin(dt*state[6])*sin(state[1])*cos(dt*state[7])*cos(state[0]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2));
   out_2069028585121272448[2] = 0;
   out_2069028585121272448[3] = 0;
   out_2069028585121272448[4] = 0;
   out_2069028585121272448[5] = 0;
   out_2069028585121272448[6] = (-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))*(dt*cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]) + (-dt*sin(dt*state[6])*sin(dt*state[8]) - dt*sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-dt*sin(dt*state[6])*cos(dt*state[8]) + dt*sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2)) + (-(sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) - sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))*(-dt*sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]) + (-dt*sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) - dt*cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (dt*sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - dt*sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2));
   out_2069028585121272448[7] = (-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))*(-dt*sin(dt*state[6])*sin(dt*state[7])*cos(state[0])*cos(state[1]) + dt*sin(dt*state[6])*sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1]) - dt*sin(dt*state[6])*sin(state[1])*cos(dt*state[7])*cos(dt*state[8]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2)) + (-(sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) - sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))*(-dt*sin(dt*state[7])*cos(dt*state[6])*cos(state[0])*cos(state[1]) + dt*sin(dt*state[8])*sin(state[0])*cos(dt*state[6])*cos(dt*state[7])*cos(state[1]) - dt*sin(state[1])*cos(dt*state[6])*cos(dt*state[7])*cos(dt*state[8]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2));
   out_2069028585121272448[8] = ((dt*sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + dt*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (dt*sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - dt*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]))*(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2)) + ((dt*sin(dt*state[6])*sin(dt*state[8]) + dt*sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (-dt*sin(dt*state[6])*cos(dt*state[8]) + dt*sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]))*(-(sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) - sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2));
   out_2069028585121272448[9] = 0;
   out_2069028585121272448[10] = 0;
   out_2069028585121272448[11] = 0;
   out_2069028585121272448[12] = 0;
   out_2069028585121272448[13] = 0;
   out_2069028585121272448[14] = 0;
   out_2069028585121272448[15] = 0;
   out_2069028585121272448[16] = 0;
   out_2069028585121272448[17] = 0;
   out_2069028585121272448[18] = (-sin(dt*state[7])*sin(state[0])*cos(state[1]) - sin(dt*state[8])*cos(dt*state[7])*cos(state[0])*cos(state[1]))/sqrt(1 - pow(sin(dt*state[7])*cos(state[0])*cos(state[1]) - sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1]) + sin(state[1])*cos(dt*state[7])*cos(dt*state[8]), 2));
   out_2069028585121272448[19] = (-sin(dt*state[7])*sin(state[1])*cos(state[0]) + sin(dt*state[8])*sin(state[0])*sin(state[1])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))/sqrt(1 - pow(sin(dt*state[7])*cos(state[0])*cos(state[1]) - sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1]) + sin(state[1])*cos(dt*state[7])*cos(dt*state[8]), 2));
   out_2069028585121272448[20] = 0;
   out_2069028585121272448[21] = 0;
   out_2069028585121272448[22] = 0;
   out_2069028585121272448[23] = 0;
   out_2069028585121272448[24] = 0;
   out_2069028585121272448[25] = (dt*sin(dt*state[7])*sin(dt*state[8])*sin(state[0])*cos(state[1]) - dt*sin(dt*state[7])*sin(state[1])*cos(dt*state[8]) + dt*cos(dt*state[7])*cos(state[0])*cos(state[1]))/sqrt(1 - pow(sin(dt*state[7])*cos(state[0])*cos(state[1]) - sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1]) + sin(state[1])*cos(dt*state[7])*cos(dt*state[8]), 2));
   out_2069028585121272448[26] = (-dt*sin(dt*state[8])*sin(state[1])*cos(dt*state[7]) - dt*sin(state[0])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))/sqrt(1 - pow(sin(dt*state[7])*cos(state[0])*cos(state[1]) - sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1]) + sin(state[1])*cos(dt*state[7])*cos(dt*state[8]), 2));
   out_2069028585121272448[27] = 0;
   out_2069028585121272448[28] = 0;
   out_2069028585121272448[29] = 0;
   out_2069028585121272448[30] = 0;
   out_2069028585121272448[31] = 0;
   out_2069028585121272448[32] = 0;
   out_2069028585121272448[33] = 0;
   out_2069028585121272448[34] = 0;
   out_2069028585121272448[35] = 0;
   out_2069028585121272448[36] = ((sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[7]))*((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) - (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) - sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2)) + ((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[7]))*(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2));
   out_2069028585121272448[37] = (-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))*(-sin(dt*state[7])*sin(state[2])*cos(state[0])*cos(state[1]) + sin(dt*state[8])*sin(state[0])*sin(state[2])*cos(dt*state[7])*cos(state[1]) - sin(state[1])*sin(state[2])*cos(dt*state[7])*cos(dt*state[8]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2)) + ((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) - (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) - sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))*(-sin(dt*state[7])*cos(state[0])*cos(state[1])*cos(state[2]) + sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1])*cos(state[2]) - sin(state[1])*cos(dt*state[7])*cos(dt*state[8])*cos(state[2]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2));
   out_2069028585121272448[38] = ((-sin(state[0])*sin(state[2]) - sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))*(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2)) + ((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (-sin(state[0])*sin(state[1])*sin(state[2]) - cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) - sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))*((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) - (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) - sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2));
   out_2069028585121272448[39] = 0;
   out_2069028585121272448[40] = 0;
   out_2069028585121272448[41] = 0;
   out_2069028585121272448[42] = 0;
   out_2069028585121272448[43] = (-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))*(dt*(sin(state[0])*cos(state[2]) - sin(state[1])*sin(state[2])*cos(state[0]))*cos(dt*state[7]) - dt*(sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[7])*sin(dt*state[8]) - dt*sin(dt*state[7])*sin(state[2])*cos(dt*state[8])*cos(state[1]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2)) + ((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) - (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) - sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))*(dt*(-sin(state[0])*sin(state[2]) - sin(state[1])*cos(state[0])*cos(state[2]))*cos(dt*state[7]) - dt*(sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[7])*sin(dt*state[8]) - dt*sin(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2));
   out_2069028585121272448[44] = (dt*(sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*cos(dt*state[7])*cos(dt*state[8]) - dt*sin(dt*state[8])*sin(state[2])*cos(dt*state[7])*cos(state[1]))*(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2)) + (dt*(sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*cos(dt*state[7])*cos(dt*state[8]) - dt*sin(dt*state[8])*cos(dt*state[7])*cos(state[1])*cos(state[2]))*((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) - (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) - sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2));
   out_2069028585121272448[45] = 0;
   out_2069028585121272448[46] = 0;
   out_2069028585121272448[47] = 0;
   out_2069028585121272448[48] = 0;
   out_2069028585121272448[49] = 0;
   out_2069028585121272448[50] = 0;
   out_2069028585121272448[51] = 0;
   out_2069028585121272448[52] = 0;
   out_2069028585121272448[53] = 0;
   out_2069028585121272448[54] = 0;
   out_2069028585121272448[55] = 0;
   out_2069028585121272448[56] = 0;
   out_2069028585121272448[57] = 1;
   out_2069028585121272448[58] = 0;
   out_2069028585121272448[59] = 0;
   out_2069028585121272448[60] = 0;
   out_2069028585121272448[61] = 0;
   out_2069028585121272448[62] = 0;
   out_2069028585121272448[63] = 0;
   out_2069028585121272448[64] = 0;
   out_2069028585121272448[65] = 0;
   out_2069028585121272448[66] = dt;
   out_2069028585121272448[67] = 0;
   out_2069028585121272448[68] = 0;
   out_2069028585121272448[69] = 0;
   out_2069028585121272448[70] = 0;
   out_2069028585121272448[71] = 0;
   out_2069028585121272448[72] = 0;
   out_2069028585121272448[73] = 0;
   out_2069028585121272448[74] = 0;
   out_2069028585121272448[75] = 0;
   out_2069028585121272448[76] = 1;
   out_2069028585121272448[77] = 0;
   out_2069028585121272448[78] = 0;
   out_2069028585121272448[79] = 0;
   out_2069028585121272448[80] = 0;
   out_2069028585121272448[81] = 0;
   out_2069028585121272448[82] = 0;
   out_2069028585121272448[83] = 0;
   out_2069028585121272448[84] = 0;
   out_2069028585121272448[85] = dt;
   out_2069028585121272448[86] = 0;
   out_2069028585121272448[87] = 0;
   out_2069028585121272448[88] = 0;
   out_2069028585121272448[89] = 0;
   out_2069028585121272448[90] = 0;
   out_2069028585121272448[91] = 0;
   out_2069028585121272448[92] = 0;
   out_2069028585121272448[93] = 0;
   out_2069028585121272448[94] = 0;
   out_2069028585121272448[95] = 1;
   out_2069028585121272448[96] = 0;
   out_2069028585121272448[97] = 0;
   out_2069028585121272448[98] = 0;
   out_2069028585121272448[99] = 0;
   out_2069028585121272448[100] = 0;
   out_2069028585121272448[101] = 0;
   out_2069028585121272448[102] = 0;
   out_2069028585121272448[103] = 0;
   out_2069028585121272448[104] = dt;
   out_2069028585121272448[105] = 0;
   out_2069028585121272448[106] = 0;
   out_2069028585121272448[107] = 0;
   out_2069028585121272448[108] = 0;
   out_2069028585121272448[109] = 0;
   out_2069028585121272448[110] = 0;
   out_2069028585121272448[111] = 0;
   out_2069028585121272448[112] = 0;
   out_2069028585121272448[113] = 0;
   out_2069028585121272448[114] = 1;
   out_2069028585121272448[115] = 0;
   out_2069028585121272448[116] = 0;
   out_2069028585121272448[117] = 0;
   out_2069028585121272448[118] = 0;
   out_2069028585121272448[119] = 0;
   out_2069028585121272448[120] = 0;
   out_2069028585121272448[121] = 0;
   out_2069028585121272448[122] = 0;
   out_2069028585121272448[123] = 0;
   out_2069028585121272448[124] = 0;
   out_2069028585121272448[125] = 0;
   out_2069028585121272448[126] = 0;
   out_2069028585121272448[127] = 0;
   out_2069028585121272448[128] = 0;
   out_2069028585121272448[129] = 0;
   out_2069028585121272448[130] = 0;
   out_2069028585121272448[131] = 0;
   out_2069028585121272448[132] = 0;
   out_2069028585121272448[133] = 1;
   out_2069028585121272448[134] = 0;
   out_2069028585121272448[135] = 0;
   out_2069028585121272448[136] = 0;
   out_2069028585121272448[137] = 0;
   out_2069028585121272448[138] = 0;
   out_2069028585121272448[139] = 0;
   out_2069028585121272448[140] = 0;
   out_2069028585121272448[141] = 0;
   out_2069028585121272448[142] = 0;
   out_2069028585121272448[143] = 0;
   out_2069028585121272448[144] = 0;
   out_2069028585121272448[145] = 0;
   out_2069028585121272448[146] = 0;
   out_2069028585121272448[147] = 0;
   out_2069028585121272448[148] = 0;
   out_2069028585121272448[149] = 0;
   out_2069028585121272448[150] = 0;
   out_2069028585121272448[151] = 0;
   out_2069028585121272448[152] = 1;
   out_2069028585121272448[153] = 0;
   out_2069028585121272448[154] = 0;
   out_2069028585121272448[155] = 0;
   out_2069028585121272448[156] = 0;
   out_2069028585121272448[157] = 0;
   out_2069028585121272448[158] = 0;
   out_2069028585121272448[159] = 0;
   out_2069028585121272448[160] = 0;
   out_2069028585121272448[161] = 0;
   out_2069028585121272448[162] = 0;
   out_2069028585121272448[163] = 0;
   out_2069028585121272448[164] = 0;
   out_2069028585121272448[165] = 0;
   out_2069028585121272448[166] = 0;
   out_2069028585121272448[167] = 0;
   out_2069028585121272448[168] = 0;
   out_2069028585121272448[169] = 0;
   out_2069028585121272448[170] = 0;
   out_2069028585121272448[171] = 1;
   out_2069028585121272448[172] = 0;
   out_2069028585121272448[173] = 0;
   out_2069028585121272448[174] = 0;
   out_2069028585121272448[175] = 0;
   out_2069028585121272448[176] = 0;
   out_2069028585121272448[177] = 0;
   out_2069028585121272448[178] = 0;
   out_2069028585121272448[179] = 0;
   out_2069028585121272448[180] = 0;
   out_2069028585121272448[181] = 0;
   out_2069028585121272448[182] = 0;
   out_2069028585121272448[183] = 0;
   out_2069028585121272448[184] = 0;
   out_2069028585121272448[185] = 0;
   out_2069028585121272448[186] = 0;
   out_2069028585121272448[187] = 0;
   out_2069028585121272448[188] = 0;
   out_2069028585121272448[189] = 0;
   out_2069028585121272448[190] = 1;
   out_2069028585121272448[191] = 0;
   out_2069028585121272448[192] = 0;
   out_2069028585121272448[193] = 0;
   out_2069028585121272448[194] = 0;
   out_2069028585121272448[195] = 0;
   out_2069028585121272448[196] = 0;
   out_2069028585121272448[197] = 0;
   out_2069028585121272448[198] = 0;
   out_2069028585121272448[199] = 0;
   out_2069028585121272448[200] = 0;
   out_2069028585121272448[201] = 0;
   out_2069028585121272448[202] = 0;
   out_2069028585121272448[203] = 0;
   out_2069028585121272448[204] = 0;
   out_2069028585121272448[205] = 0;
   out_2069028585121272448[206] = 0;
   out_2069028585121272448[207] = 0;
   out_2069028585121272448[208] = 0;
   out_2069028585121272448[209] = 1;
   out_2069028585121272448[210] = 0;
   out_2069028585121272448[211] = 0;
   out_2069028585121272448[212] = 0;
   out_2069028585121272448[213] = 0;
   out_2069028585121272448[214] = 0;
   out_2069028585121272448[215] = 0;
   out_2069028585121272448[216] = 0;
   out_2069028585121272448[217] = 0;
   out_2069028585121272448[218] = 0;
   out_2069028585121272448[219] = 0;
   out_2069028585121272448[220] = 0;
   out_2069028585121272448[221] = 0;
   out_2069028585121272448[222] = 0;
   out_2069028585121272448[223] = 0;
   out_2069028585121272448[224] = 0;
   out_2069028585121272448[225] = 0;
   out_2069028585121272448[226] = 0;
   out_2069028585121272448[227] = 0;
   out_2069028585121272448[228] = 1;
   out_2069028585121272448[229] = 0;
   out_2069028585121272448[230] = 0;
   out_2069028585121272448[231] = 0;
   out_2069028585121272448[232] = 0;
   out_2069028585121272448[233] = 0;
   out_2069028585121272448[234] = 0;
   out_2069028585121272448[235] = 0;
   out_2069028585121272448[236] = 0;
   out_2069028585121272448[237] = 0;
   out_2069028585121272448[238] = 0;
   out_2069028585121272448[239] = 0;
   out_2069028585121272448[240] = 0;
   out_2069028585121272448[241] = 0;
   out_2069028585121272448[242] = 0;
   out_2069028585121272448[243] = 0;
   out_2069028585121272448[244] = 0;
   out_2069028585121272448[245] = 0;
   out_2069028585121272448[246] = 0;
   out_2069028585121272448[247] = 1;
   out_2069028585121272448[248] = 0;
   out_2069028585121272448[249] = 0;
   out_2069028585121272448[250] = 0;
   out_2069028585121272448[251] = 0;
   out_2069028585121272448[252] = 0;
   out_2069028585121272448[253] = 0;
   out_2069028585121272448[254] = 0;
   out_2069028585121272448[255] = 0;
   out_2069028585121272448[256] = 0;
   out_2069028585121272448[257] = 0;
   out_2069028585121272448[258] = 0;
   out_2069028585121272448[259] = 0;
   out_2069028585121272448[260] = 0;
   out_2069028585121272448[261] = 0;
   out_2069028585121272448[262] = 0;
   out_2069028585121272448[263] = 0;
   out_2069028585121272448[264] = 0;
   out_2069028585121272448[265] = 0;
   out_2069028585121272448[266] = 1;
   out_2069028585121272448[267] = 0;
   out_2069028585121272448[268] = 0;
   out_2069028585121272448[269] = 0;
   out_2069028585121272448[270] = 0;
   out_2069028585121272448[271] = 0;
   out_2069028585121272448[272] = 0;
   out_2069028585121272448[273] = 0;
   out_2069028585121272448[274] = 0;
   out_2069028585121272448[275] = 0;
   out_2069028585121272448[276] = 0;
   out_2069028585121272448[277] = 0;
   out_2069028585121272448[278] = 0;
   out_2069028585121272448[279] = 0;
   out_2069028585121272448[280] = 0;
   out_2069028585121272448[281] = 0;
   out_2069028585121272448[282] = 0;
   out_2069028585121272448[283] = 0;
   out_2069028585121272448[284] = 0;
   out_2069028585121272448[285] = 1;
   out_2069028585121272448[286] = 0;
   out_2069028585121272448[287] = 0;
   out_2069028585121272448[288] = 0;
   out_2069028585121272448[289] = 0;
   out_2069028585121272448[290] = 0;
   out_2069028585121272448[291] = 0;
   out_2069028585121272448[292] = 0;
   out_2069028585121272448[293] = 0;
   out_2069028585121272448[294] = 0;
   out_2069028585121272448[295] = 0;
   out_2069028585121272448[296] = 0;
   out_2069028585121272448[297] = 0;
   out_2069028585121272448[298] = 0;
   out_2069028585121272448[299] = 0;
   out_2069028585121272448[300] = 0;
   out_2069028585121272448[301] = 0;
   out_2069028585121272448[302] = 0;
   out_2069028585121272448[303] = 0;
   out_2069028585121272448[304] = 1;
   out_2069028585121272448[305] = 0;
   out_2069028585121272448[306] = 0;
   out_2069028585121272448[307] = 0;
   out_2069028585121272448[308] = 0;
   out_2069028585121272448[309] = 0;
   out_2069028585121272448[310] = 0;
   out_2069028585121272448[311] = 0;
   out_2069028585121272448[312] = 0;
   out_2069028585121272448[313] = 0;
   out_2069028585121272448[314] = 0;
   out_2069028585121272448[315] = 0;
   out_2069028585121272448[316] = 0;
   out_2069028585121272448[317] = 0;
   out_2069028585121272448[318] = 0;
   out_2069028585121272448[319] = 0;
   out_2069028585121272448[320] = 0;
   out_2069028585121272448[321] = 0;
   out_2069028585121272448[322] = 0;
   out_2069028585121272448[323] = 1;
}
void h_4(double *state, double *unused, double *out_8602233424768964049) {
   out_8602233424768964049[0] = state[6] + state[9];
   out_8602233424768964049[1] = state[7] + state[10];
   out_8602233424768964049[2] = state[8] + state[11];
}
void H_4(double *state, double *unused, double *out_4633898163307387933) {
   out_4633898163307387933[0] = 0;
   out_4633898163307387933[1] = 0;
   out_4633898163307387933[2] = 0;
   out_4633898163307387933[3] = 0;
   out_4633898163307387933[4] = 0;
   out_4633898163307387933[5] = 0;
   out_4633898163307387933[6] = 1;
   out_4633898163307387933[7] = 0;
   out_4633898163307387933[8] = 0;
   out_4633898163307387933[9] = 1;
   out_4633898163307387933[10] = 0;
   out_4633898163307387933[11] = 0;
   out_4633898163307387933[12] = 0;
   out_4633898163307387933[13] = 0;
   out_4633898163307387933[14] = 0;
   out_4633898163307387933[15] = 0;
   out_4633898163307387933[16] = 0;
   out_4633898163307387933[17] = 0;
   out_4633898163307387933[18] = 0;
   out_4633898163307387933[19] = 0;
   out_4633898163307387933[20] = 0;
   out_4633898163307387933[21] = 0;
   out_4633898163307387933[22] = 0;
   out_4633898163307387933[23] = 0;
   out_4633898163307387933[24] = 0;
   out_4633898163307387933[25] = 1;
   out_4633898163307387933[26] = 0;
   out_4633898163307387933[27] = 0;
   out_4633898163307387933[28] = 1;
   out_4633898163307387933[29] = 0;
   out_4633898163307387933[30] = 0;
   out_4633898163307387933[31] = 0;
   out_4633898163307387933[32] = 0;
   out_4633898163307387933[33] = 0;
   out_4633898163307387933[34] = 0;
   out_4633898163307387933[35] = 0;
   out_4633898163307387933[36] = 0;
   out_4633898163307387933[37] = 0;
   out_4633898163307387933[38] = 0;
   out_4633898163307387933[39] = 0;
   out_4633898163307387933[40] = 0;
   out_4633898163307387933[41] = 0;
   out_4633898163307387933[42] = 0;
   out_4633898163307387933[43] = 0;
   out_4633898163307387933[44] = 1;
   out_4633898163307387933[45] = 0;
   out_4633898163307387933[46] = 0;
   out_4633898163307387933[47] = 1;
   out_4633898163307387933[48] = 0;
   out_4633898163307387933[49] = 0;
   out_4633898163307387933[50] = 0;
   out_4633898163307387933[51] = 0;
   out_4633898163307387933[52] = 0;
   out_4633898163307387933[53] = 0;
}
void h_10(double *state, double *unused, double *out_4500317655482818027) {
   out_4500317655482818027[0] = 9.8100000000000005*sin(state[1]) - state[4]*state[8] + state[5]*state[7] + state[12] + state[15];
   out_4500317655482818027[1] = -9.8100000000000005*sin(state[0])*cos(state[1]) + state[3]*state[8] - state[5]*state[6] + state[13] + state[16];
   out_4500317655482818027[2] = -9.8100000000000005*cos(state[0])*cos(state[1]) - state[3]*state[7] + state[4]*state[6] + state[14] + state[17];
}
void H_10(double *state, double *unused, double *out_2288732070358272906) {
   out_2288732070358272906[0] = 0;
   out_2288732070358272906[1] = 9.8100000000000005*cos(state[1]);
   out_2288732070358272906[2] = 0;
   out_2288732070358272906[3] = 0;
   out_2288732070358272906[4] = -state[8];
   out_2288732070358272906[5] = state[7];
   out_2288732070358272906[6] = 0;
   out_2288732070358272906[7] = state[5];
   out_2288732070358272906[8] = -state[4];
   out_2288732070358272906[9] = 0;
   out_2288732070358272906[10] = 0;
   out_2288732070358272906[11] = 0;
   out_2288732070358272906[12] = 1;
   out_2288732070358272906[13] = 0;
   out_2288732070358272906[14] = 0;
   out_2288732070358272906[15] = 1;
   out_2288732070358272906[16] = 0;
   out_2288732070358272906[17] = 0;
   out_2288732070358272906[18] = -9.8100000000000005*cos(state[0])*cos(state[1]);
   out_2288732070358272906[19] = 9.8100000000000005*sin(state[0])*sin(state[1]);
   out_2288732070358272906[20] = 0;
   out_2288732070358272906[21] = state[8];
   out_2288732070358272906[22] = 0;
   out_2288732070358272906[23] = -state[6];
   out_2288732070358272906[24] = -state[5];
   out_2288732070358272906[25] = 0;
   out_2288732070358272906[26] = state[3];
   out_2288732070358272906[27] = 0;
   out_2288732070358272906[28] = 0;
   out_2288732070358272906[29] = 0;
   out_2288732070358272906[30] = 0;
   out_2288732070358272906[31] = 1;
   out_2288732070358272906[32] = 0;
   out_2288732070358272906[33] = 0;
   out_2288732070358272906[34] = 1;
   out_2288732070358272906[35] = 0;
   out_2288732070358272906[36] = 9.8100000000000005*sin(state[0])*cos(state[1]);
   out_2288732070358272906[37] = 9.8100000000000005*sin(state[1])*cos(state[0]);
   out_2288732070358272906[38] = 0;
   out_2288732070358272906[39] = -state[7];
   out_2288732070358272906[40] = state[6];
   out_2288732070358272906[41] = 0;
   out_2288732070358272906[42] = state[4];
   out_2288732070358272906[43] = -state[3];
   out_2288732070358272906[44] = 0;
   out_2288732070358272906[45] = 0;
   out_2288732070358272906[46] = 0;
   out_2288732070358272906[47] = 0;
   out_2288732070358272906[48] = 0;
   out_2288732070358272906[49] = 0;
   out_2288732070358272906[50] = 1;
   out_2288732070358272906[51] = 0;
   out_2288732070358272906[52] = 0;
   out_2288732070358272906[53] = 1;
}
void h_13(double *state, double *unused, double *out_6663006413571036728) {
   out_6663006413571036728[0] = state[3];
   out_6663006413571036728[1] = state[4];
   out_6663006413571036728[2] = state[5];
}
void H_13(double *state, double *unused, double *out_7846171988639720734) {
   out_7846171988639720734[0] = 0;
   out_7846171988639720734[1] = 0;
   out_7846171988639720734[2] = 0;
   out_7846171988639720734[3] = 1;
   out_7846171988639720734[4] = 0;
   out_7846171988639720734[5] = 0;
   out_7846171988639720734[6] = 0;
   out_7846171988639720734[7] = 0;
   out_7846171988639720734[8] = 0;
   out_7846171988639720734[9] = 0;
   out_7846171988639720734[10] = 0;
   out_7846171988639720734[11] = 0;
   out_7846171988639720734[12] = 0;
   out_7846171988639720734[13] = 0;
   out_7846171988639720734[14] = 0;
   out_7846171988639720734[15] = 0;
   out_7846171988639720734[16] = 0;
   out_7846171988639720734[17] = 0;
   out_7846171988639720734[18] = 0;
   out_7846171988639720734[19] = 0;
   out_7846171988639720734[20] = 0;
   out_7846171988639720734[21] = 0;
   out_7846171988639720734[22] = 1;
   out_7846171988639720734[23] = 0;
   out_7846171988639720734[24] = 0;
   out_7846171988639720734[25] = 0;
   out_7846171988639720734[26] = 0;
   out_7846171988639720734[27] = 0;
   out_7846171988639720734[28] = 0;
   out_7846171988639720734[29] = 0;
   out_7846171988639720734[30] = 0;
   out_7846171988639720734[31] = 0;
   out_7846171988639720734[32] = 0;
   out_7846171988639720734[33] = 0;
   out_7846171988639720734[34] = 0;
   out_7846171988639720734[35] = 0;
   out_7846171988639720734[36] = 0;
   out_7846171988639720734[37] = 0;
   out_7846171988639720734[38] = 0;
   out_7846171988639720734[39] = 0;
   out_7846171988639720734[40] = 0;
   out_7846171988639720734[41] = 1;
   out_7846171988639720734[42] = 0;
   out_7846171988639720734[43] = 0;
   out_7846171988639720734[44] = 0;
   out_7846171988639720734[45] = 0;
   out_7846171988639720734[46] = 0;
   out_7846171988639720734[47] = 0;
   out_7846171988639720734[48] = 0;
   out_7846171988639720734[49] = 0;
   out_7846171988639720734[50] = 0;
   out_7846171988639720734[51] = 0;
   out_7846171988639720734[52] = 0;
   out_7846171988639720734[53] = 0;
}
void h_14(double *state, double *unused, double *out_8667838621540344432) {
   out_8667838621540344432[0] = state[6];
   out_8667838621540344432[1] = state[7];
   out_8667838621540344432[2] = state[8];
}
void H_14(double *state, double *unused, double *out_1551109731012015637) {
   out_1551109731012015637[0] = 0;
   out_1551109731012015637[1] = 0;
   out_1551109731012015637[2] = 0;
   out_1551109731012015637[3] = 0;
   out_1551109731012015637[4] = 0;
   out_1551109731012015637[5] = 0;
   out_1551109731012015637[6] = 1;
   out_1551109731012015637[7] = 0;
   out_1551109731012015637[8] = 0;
   out_1551109731012015637[9] = 0;
   out_1551109731012015637[10] = 0;
   out_1551109731012015637[11] = 0;
   out_1551109731012015637[12] = 0;
   out_1551109731012015637[13] = 0;
   out_1551109731012015637[14] = 0;
   out_1551109731012015637[15] = 0;
   out_1551109731012015637[16] = 0;
   out_1551109731012015637[17] = 0;
   out_1551109731012015637[18] = 0;
   out_1551109731012015637[19] = 0;
   out_1551109731012015637[20] = 0;
   out_1551109731012015637[21] = 0;
   out_1551109731012015637[22] = 0;
   out_1551109731012015637[23] = 0;
   out_1551109731012015637[24] = 0;
   out_1551109731012015637[25] = 1;
   out_1551109731012015637[26] = 0;
   out_1551109731012015637[27] = 0;
   out_1551109731012015637[28] = 0;
   out_1551109731012015637[29] = 0;
   out_1551109731012015637[30] = 0;
   out_1551109731012015637[31] = 0;
   out_1551109731012015637[32] = 0;
   out_1551109731012015637[33] = 0;
   out_1551109731012015637[34] = 0;
   out_1551109731012015637[35] = 0;
   out_1551109731012015637[36] = 0;
   out_1551109731012015637[37] = 0;
   out_1551109731012015637[38] = 0;
   out_1551109731012015637[39] = 0;
   out_1551109731012015637[40] = 0;
   out_1551109731012015637[41] = 0;
   out_1551109731012015637[42] = 0;
   out_1551109731012015637[43] = 0;
   out_1551109731012015637[44] = 1;
   out_1551109731012015637[45] = 0;
   out_1551109731012015637[46] = 0;
   out_1551109731012015637[47] = 0;
   out_1551109731012015637[48] = 0;
   out_1551109731012015637[49] = 0;
   out_1551109731012015637[50] = 0;
   out_1551109731012015637[51] = 0;
   out_1551109731012015637[52] = 0;
   out_1551109731012015637[53] = 0;
}
#include <eigen3/Eigen/Dense>
#include <iostream>

typedef Eigen::Matrix<double, DIM, DIM, Eigen::RowMajor> DDM;
typedef Eigen::Matrix<double, EDIM, EDIM, Eigen::RowMajor> EEM;
typedef Eigen::Matrix<double, DIM, EDIM, Eigen::RowMajor> DEM;

void predict(double *in_x, double *in_P, double *in_Q, double dt) {
  typedef Eigen::Matrix<double, MEDIM, MEDIM, Eigen::RowMajor> RRM;

  double nx[DIM] = {0};
  double in_F[EDIM*EDIM] = {0};

  // functions from sympy
  f_fun(in_x, dt, nx);
  F_fun(in_x, dt, in_F);


  EEM F(in_F);
  EEM P(in_P);
  EEM Q(in_Q);

  RRM F_main = F.topLeftCorner(MEDIM, MEDIM);
  P.topLeftCorner(MEDIM, MEDIM) = (F_main * P.topLeftCorner(MEDIM, MEDIM)) * F_main.transpose();
  P.topRightCorner(MEDIM, EDIM - MEDIM) = F_main * P.topRightCorner(MEDIM, EDIM - MEDIM);
  P.bottomLeftCorner(EDIM - MEDIM, MEDIM) = P.bottomLeftCorner(EDIM - MEDIM, MEDIM) * F_main.transpose();

  P = P + dt*Q;

  // copy out state
  memcpy(in_x, nx, DIM * sizeof(double));
  memcpy(in_P, P.data(), EDIM * EDIM * sizeof(double));
}

// note: extra_args dim only correct when null space projecting
// otherwise 1
template <int ZDIM, int EADIM, bool MAHA_TEST>
void update(double *in_x, double *in_P, Hfun h_fun, Hfun H_fun, Hfun Hea_fun, double *in_z, double *in_R, double *in_ea, double MAHA_THRESHOLD) {
  typedef Eigen::Matrix<double, ZDIM, ZDIM, Eigen::RowMajor> ZZM;
  typedef Eigen::Matrix<double, ZDIM, DIM, Eigen::RowMajor> ZDM;
  typedef Eigen::Matrix<double, Eigen::Dynamic, EDIM, Eigen::RowMajor> XEM;
  //typedef Eigen::Matrix<double, EDIM, ZDIM, Eigen::RowMajor> EZM;
  typedef Eigen::Matrix<double, Eigen::Dynamic, 1> X1M;
  typedef Eigen::Matrix<double, Eigen::Dynamic, Eigen::Dynamic, Eigen::RowMajor> XXM;

  double in_hx[ZDIM] = {0};
  double in_H[ZDIM * DIM] = {0};
  double in_H_mod[EDIM * DIM] = {0};
  double delta_x[EDIM] = {0};
  double x_new[DIM] = {0};


  // state x, P
  Eigen::Matrix<double, ZDIM, 1> z(in_z);
  EEM P(in_P);
  ZZM pre_R(in_R);

  // functions from sympy
  h_fun(in_x, in_ea, in_hx);
  H_fun(in_x, in_ea, in_H);
  ZDM pre_H(in_H);

  // get y (y = z - hx)
  Eigen::Matrix<double, ZDIM, 1> pre_y(in_hx); pre_y = z - pre_y;
  X1M y; XXM H; XXM R;
  if (Hea_fun){
    typedef Eigen::Matrix<double, ZDIM, EADIM, Eigen::RowMajor> ZAM;
    double in_Hea[ZDIM * EADIM] = {0};
    Hea_fun(in_x, in_ea, in_Hea);
    ZAM Hea(in_Hea);
    XXM A = Hea.transpose().fullPivLu().kernel();


    y = A.transpose() * pre_y;
    H = A.transpose() * pre_H;
    R = A.transpose() * pre_R * A;
  } else {
    y = pre_y;
    H = pre_H;
    R = pre_R;
  }
  // get modified H
  H_mod_fun(in_x, in_H_mod);
  DEM H_mod(in_H_mod);
  XEM H_err = H * H_mod;

  // Do mahalobis distance test
  if (MAHA_TEST){
    XXM a = (H_err * P * H_err.transpose() + R).inverse();
    double maha_dist = y.transpose() * a * y;
    if (maha_dist > MAHA_THRESHOLD){
      R = 1.0e16 * R;
    }
  }

  // Outlier resilient weighting
  double weight = 1;//(1.5)/(1 + y.squaredNorm()/R.sum());

  // kalman gains and I_KH
  XXM S = ((H_err * P) * H_err.transpose()) + R/weight;
  XEM KT = S.fullPivLu().solve(H_err * P.transpose());
  //EZM K = KT.transpose(); TODO: WHY DOES THIS NOT COMPILE?
  //EZM K = S.fullPivLu().solve(H_err * P.transpose()).transpose();
  //std::cout << "Here is the matrix rot:\n" << K << std::endl;
  EEM I_KH = Eigen::Matrix<double, EDIM, EDIM>::Identity() - (KT.transpose() * H_err);

  // update state by injecting dx
  Eigen::Matrix<double, EDIM, 1> dx(delta_x);
  dx  = (KT.transpose() * y);
  memcpy(delta_x, dx.data(), EDIM * sizeof(double));
  err_fun(in_x, delta_x, x_new);
  Eigen::Matrix<double, DIM, 1> x(x_new);

  // update cov
  P = ((I_KH * P) * I_KH.transpose()) + ((KT.transpose() * R) * KT);

  // copy out state
  memcpy(in_x, x.data(), DIM * sizeof(double));
  memcpy(in_P, P.data(), EDIM * EDIM * sizeof(double));
  memcpy(in_z, y.data(), y.rows() * sizeof(double));
}




}
extern "C" {

void pose_update_4(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<3, 3, 0>(in_x, in_P, h_4, H_4, NULL, in_z, in_R, in_ea, MAHA_THRESH_4);
}
void pose_update_10(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<3, 3, 0>(in_x, in_P, h_10, H_10, NULL, in_z, in_R, in_ea, MAHA_THRESH_10);
}
void pose_update_13(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<3, 3, 0>(in_x, in_P, h_13, H_13, NULL, in_z, in_R, in_ea, MAHA_THRESH_13);
}
void pose_update_14(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<3, 3, 0>(in_x, in_P, h_14, H_14, NULL, in_z, in_R, in_ea, MAHA_THRESH_14);
}
void pose_err_fun(double *nom_x, double *delta_x, double *out_1302557212303107234) {
  err_fun(nom_x, delta_x, out_1302557212303107234);
}
void pose_inv_err_fun(double *nom_x, double *true_x, double *out_645935160919976454) {
  inv_err_fun(nom_x, true_x, out_645935160919976454);
}
void pose_H_mod_fun(double *state, double *out_3435950681424489829) {
  H_mod_fun(state, out_3435950681424489829);
}
void pose_f_fun(double *state, double dt, double *out_5840201724917908869) {
  f_fun(state,  dt, out_5840201724917908869);
}
void pose_F_fun(double *state, double dt, double *out_2069028585121272448) {
  F_fun(state,  dt, out_2069028585121272448);
}
void pose_h_4(double *state, double *unused, double *out_8602233424768964049) {
  h_4(state, unused, out_8602233424768964049);
}
void pose_H_4(double *state, double *unused, double *out_4633898163307387933) {
  H_4(state, unused, out_4633898163307387933);
}
void pose_h_10(double *state, double *unused, double *out_4500317655482818027) {
  h_10(state, unused, out_4500317655482818027);
}
void pose_H_10(double *state, double *unused, double *out_2288732070358272906) {
  H_10(state, unused, out_2288732070358272906);
}
void pose_h_13(double *state, double *unused, double *out_6663006413571036728) {
  h_13(state, unused, out_6663006413571036728);
}
void pose_H_13(double *state, double *unused, double *out_7846171988639720734) {
  H_13(state, unused, out_7846171988639720734);
}
void pose_h_14(double *state, double *unused, double *out_8667838621540344432) {
  h_14(state, unused, out_8667838621540344432);
}
void pose_H_14(double *state, double *unused, double *out_1551109731012015637) {
  H_14(state, unused, out_1551109731012015637);
}
void pose_predict(double *in_x, double *in_P, double *in_Q, double dt) {
  predict(in_x, in_P, in_Q, dt);
}
}

const EKF pose = {
  .name = "pose",
  .kinds = { 4, 10, 13, 14 },
  .feature_kinds = {  },
  .f_fun = pose_f_fun,
  .F_fun = pose_F_fun,
  .err_fun = pose_err_fun,
  .inv_err_fun = pose_inv_err_fun,
  .H_mod_fun = pose_H_mod_fun,
  .predict = pose_predict,
  .hs = {
    { 4, pose_h_4 },
    { 10, pose_h_10 },
    { 13, pose_h_13 },
    { 14, pose_h_14 },
  },
  .Hs = {
    { 4, pose_H_4 },
    { 10, pose_H_10 },
    { 13, pose_H_13 },
    { 14, pose_H_14 },
  },
  .updates = {
    { 4, pose_update_4 },
    { 10, pose_update_10 },
    { 13, pose_update_13 },
    { 14, pose_update_14 },
  },
  .Hes = {
  },
  .sets = {
  },
  .extra_routines = {
  },
};

ekf_lib_init(pose)
