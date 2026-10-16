#include "car.h"

namespace {
#define DIM 9
#define EDIM 9
#define MEDIM 9
typedef void (*Hfun)(double *, double *, double *);

double mass;

void set_mass(double x){ mass = x;}

double rotational_inertia;

void set_rotational_inertia(double x){ rotational_inertia = x;}

double center_to_front;

void set_center_to_front(double x){ center_to_front = x;}

double center_to_rear;

void set_center_to_rear(double x){ center_to_rear = x;}

double stiffness_front;

void set_stiffness_front(double x){ stiffness_front = x;}

double stiffness_rear;

void set_stiffness_rear(double x){ stiffness_rear = x;}
const static double MAHA_THRESH_25 = 3.8414588206941227;
const static double MAHA_THRESH_24 = 5.991464547107981;
const static double MAHA_THRESH_30 = 3.8414588206941227;
const static double MAHA_THRESH_26 = 3.8414588206941227;
const static double MAHA_THRESH_27 = 3.8414588206941227;
const static double MAHA_THRESH_29 = 3.8414588206941227;
const static double MAHA_THRESH_28 = 3.8414588206941227;
const static double MAHA_THRESH_31 = 3.8414588206941227;

/******************************************************************************
 *                      Code generated with SymPy 1.14.0                      *
 *                                                                            *
 *              See http://www.sympy.org/ for more information.               *
 *                                                                            *
 *                         This file is part of 'ekf'                         *
 ******************************************************************************/
void err_fun(double *nom_x, double *delta_x, double *out_7807431280886572175) {
   out_7807431280886572175[0] = delta_x[0] + nom_x[0];
   out_7807431280886572175[1] = delta_x[1] + nom_x[1];
   out_7807431280886572175[2] = delta_x[2] + nom_x[2];
   out_7807431280886572175[3] = delta_x[3] + nom_x[3];
   out_7807431280886572175[4] = delta_x[4] + nom_x[4];
   out_7807431280886572175[5] = delta_x[5] + nom_x[5];
   out_7807431280886572175[6] = delta_x[6] + nom_x[6];
   out_7807431280886572175[7] = delta_x[7] + nom_x[7];
   out_7807431280886572175[8] = delta_x[8] + nom_x[8];
}
void inv_err_fun(double *nom_x, double *true_x, double *out_6108977637297046258) {
   out_6108977637297046258[0] = -nom_x[0] + true_x[0];
   out_6108977637297046258[1] = -nom_x[1] + true_x[1];
   out_6108977637297046258[2] = -nom_x[2] + true_x[2];
   out_6108977637297046258[3] = -nom_x[3] + true_x[3];
   out_6108977637297046258[4] = -nom_x[4] + true_x[4];
   out_6108977637297046258[5] = -nom_x[5] + true_x[5];
   out_6108977637297046258[6] = -nom_x[6] + true_x[6];
   out_6108977637297046258[7] = -nom_x[7] + true_x[7];
   out_6108977637297046258[8] = -nom_x[8] + true_x[8];
}
void H_mod_fun(double *state, double *out_7863625486438816874) {
   out_7863625486438816874[0] = 1.0;
   out_7863625486438816874[1] = 0.0;
   out_7863625486438816874[2] = 0.0;
   out_7863625486438816874[3] = 0.0;
   out_7863625486438816874[4] = 0.0;
   out_7863625486438816874[5] = 0.0;
   out_7863625486438816874[6] = 0.0;
   out_7863625486438816874[7] = 0.0;
   out_7863625486438816874[8] = 0.0;
   out_7863625486438816874[9] = 0.0;
   out_7863625486438816874[10] = 1.0;
   out_7863625486438816874[11] = 0.0;
   out_7863625486438816874[12] = 0.0;
   out_7863625486438816874[13] = 0.0;
   out_7863625486438816874[14] = 0.0;
   out_7863625486438816874[15] = 0.0;
   out_7863625486438816874[16] = 0.0;
   out_7863625486438816874[17] = 0.0;
   out_7863625486438816874[18] = 0.0;
   out_7863625486438816874[19] = 0.0;
   out_7863625486438816874[20] = 1.0;
   out_7863625486438816874[21] = 0.0;
   out_7863625486438816874[22] = 0.0;
   out_7863625486438816874[23] = 0.0;
   out_7863625486438816874[24] = 0.0;
   out_7863625486438816874[25] = 0.0;
   out_7863625486438816874[26] = 0.0;
   out_7863625486438816874[27] = 0.0;
   out_7863625486438816874[28] = 0.0;
   out_7863625486438816874[29] = 0.0;
   out_7863625486438816874[30] = 1.0;
   out_7863625486438816874[31] = 0.0;
   out_7863625486438816874[32] = 0.0;
   out_7863625486438816874[33] = 0.0;
   out_7863625486438816874[34] = 0.0;
   out_7863625486438816874[35] = 0.0;
   out_7863625486438816874[36] = 0.0;
   out_7863625486438816874[37] = 0.0;
   out_7863625486438816874[38] = 0.0;
   out_7863625486438816874[39] = 0.0;
   out_7863625486438816874[40] = 1.0;
   out_7863625486438816874[41] = 0.0;
   out_7863625486438816874[42] = 0.0;
   out_7863625486438816874[43] = 0.0;
   out_7863625486438816874[44] = 0.0;
   out_7863625486438816874[45] = 0.0;
   out_7863625486438816874[46] = 0.0;
   out_7863625486438816874[47] = 0.0;
   out_7863625486438816874[48] = 0.0;
   out_7863625486438816874[49] = 0.0;
   out_7863625486438816874[50] = 1.0;
   out_7863625486438816874[51] = 0.0;
   out_7863625486438816874[52] = 0.0;
   out_7863625486438816874[53] = 0.0;
   out_7863625486438816874[54] = 0.0;
   out_7863625486438816874[55] = 0.0;
   out_7863625486438816874[56] = 0.0;
   out_7863625486438816874[57] = 0.0;
   out_7863625486438816874[58] = 0.0;
   out_7863625486438816874[59] = 0.0;
   out_7863625486438816874[60] = 1.0;
   out_7863625486438816874[61] = 0.0;
   out_7863625486438816874[62] = 0.0;
   out_7863625486438816874[63] = 0.0;
   out_7863625486438816874[64] = 0.0;
   out_7863625486438816874[65] = 0.0;
   out_7863625486438816874[66] = 0.0;
   out_7863625486438816874[67] = 0.0;
   out_7863625486438816874[68] = 0.0;
   out_7863625486438816874[69] = 0.0;
   out_7863625486438816874[70] = 1.0;
   out_7863625486438816874[71] = 0.0;
   out_7863625486438816874[72] = 0.0;
   out_7863625486438816874[73] = 0.0;
   out_7863625486438816874[74] = 0.0;
   out_7863625486438816874[75] = 0.0;
   out_7863625486438816874[76] = 0.0;
   out_7863625486438816874[77] = 0.0;
   out_7863625486438816874[78] = 0.0;
   out_7863625486438816874[79] = 0.0;
   out_7863625486438816874[80] = 1.0;
}
void f_fun(double *state, double dt, double *out_5659262996305498661) {
   out_5659262996305498661[0] = state[0];
   out_5659262996305498661[1] = state[1];
   out_5659262996305498661[2] = state[2];
   out_5659262996305498661[3] = state[3];
   out_5659262996305498661[4] = state[4];
   out_5659262996305498661[5] = dt*((-state[4] + (-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])/(mass*state[4]))*state[6] - 9.8100000000000005*state[8] + stiffness_front*(-state[2] - state[3] + state[7])*state[0]/(mass*state[1]) + (-stiffness_front*state[0] - stiffness_rear*state[0])*state[5]/(mass*state[4])) + state[5];
   out_5659262996305498661[6] = dt*(center_to_front*stiffness_front*(-state[2] - state[3] + state[7])*state[0]/(rotational_inertia*state[1]) + (-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])*state[5]/(rotational_inertia*state[4]) + (-pow(center_to_front, 2)*stiffness_front*state[0] - pow(center_to_rear, 2)*stiffness_rear*state[0])*state[6]/(rotational_inertia*state[4])) + state[6];
   out_5659262996305498661[7] = state[7];
   out_5659262996305498661[8] = state[8];
}
void F_fun(double *state, double dt, double *out_408343791691886305) {
   out_408343791691886305[0] = 1;
   out_408343791691886305[1] = 0;
   out_408343791691886305[2] = 0;
   out_408343791691886305[3] = 0;
   out_408343791691886305[4] = 0;
   out_408343791691886305[5] = 0;
   out_408343791691886305[6] = 0;
   out_408343791691886305[7] = 0;
   out_408343791691886305[8] = 0;
   out_408343791691886305[9] = 0;
   out_408343791691886305[10] = 1;
   out_408343791691886305[11] = 0;
   out_408343791691886305[12] = 0;
   out_408343791691886305[13] = 0;
   out_408343791691886305[14] = 0;
   out_408343791691886305[15] = 0;
   out_408343791691886305[16] = 0;
   out_408343791691886305[17] = 0;
   out_408343791691886305[18] = 0;
   out_408343791691886305[19] = 0;
   out_408343791691886305[20] = 1;
   out_408343791691886305[21] = 0;
   out_408343791691886305[22] = 0;
   out_408343791691886305[23] = 0;
   out_408343791691886305[24] = 0;
   out_408343791691886305[25] = 0;
   out_408343791691886305[26] = 0;
   out_408343791691886305[27] = 0;
   out_408343791691886305[28] = 0;
   out_408343791691886305[29] = 0;
   out_408343791691886305[30] = 1;
   out_408343791691886305[31] = 0;
   out_408343791691886305[32] = 0;
   out_408343791691886305[33] = 0;
   out_408343791691886305[34] = 0;
   out_408343791691886305[35] = 0;
   out_408343791691886305[36] = 0;
   out_408343791691886305[37] = 0;
   out_408343791691886305[38] = 0;
   out_408343791691886305[39] = 0;
   out_408343791691886305[40] = 1;
   out_408343791691886305[41] = 0;
   out_408343791691886305[42] = 0;
   out_408343791691886305[43] = 0;
   out_408343791691886305[44] = 0;
   out_408343791691886305[45] = dt*(stiffness_front*(-state[2] - state[3] + state[7])/(mass*state[1]) + (-stiffness_front - stiffness_rear)*state[5]/(mass*state[4]) + (-center_to_front*stiffness_front + center_to_rear*stiffness_rear)*state[6]/(mass*state[4]));
   out_408343791691886305[46] = -dt*stiffness_front*(-state[2] - state[3] + state[7])*state[0]/(mass*pow(state[1], 2));
   out_408343791691886305[47] = -dt*stiffness_front*state[0]/(mass*state[1]);
   out_408343791691886305[48] = -dt*stiffness_front*state[0]/(mass*state[1]);
   out_408343791691886305[49] = dt*((-1 - (-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])/(mass*pow(state[4], 2)))*state[6] - (-stiffness_front*state[0] - stiffness_rear*state[0])*state[5]/(mass*pow(state[4], 2)));
   out_408343791691886305[50] = dt*(-stiffness_front*state[0] - stiffness_rear*state[0])/(mass*state[4]) + 1;
   out_408343791691886305[51] = dt*(-state[4] + (-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])/(mass*state[4]));
   out_408343791691886305[52] = dt*stiffness_front*state[0]/(mass*state[1]);
   out_408343791691886305[53] = -9.8100000000000005*dt;
   out_408343791691886305[54] = dt*(center_to_front*stiffness_front*(-state[2] - state[3] + state[7])/(rotational_inertia*state[1]) + (-center_to_front*stiffness_front + center_to_rear*stiffness_rear)*state[5]/(rotational_inertia*state[4]) + (-pow(center_to_front, 2)*stiffness_front - pow(center_to_rear, 2)*stiffness_rear)*state[6]/(rotational_inertia*state[4]));
   out_408343791691886305[55] = -center_to_front*dt*stiffness_front*(-state[2] - state[3] + state[7])*state[0]/(rotational_inertia*pow(state[1], 2));
   out_408343791691886305[56] = -center_to_front*dt*stiffness_front*state[0]/(rotational_inertia*state[1]);
   out_408343791691886305[57] = -center_to_front*dt*stiffness_front*state[0]/(rotational_inertia*state[1]);
   out_408343791691886305[58] = dt*(-(-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])*state[5]/(rotational_inertia*pow(state[4], 2)) - (-pow(center_to_front, 2)*stiffness_front*state[0] - pow(center_to_rear, 2)*stiffness_rear*state[0])*state[6]/(rotational_inertia*pow(state[4], 2)));
   out_408343791691886305[59] = dt*(-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])/(rotational_inertia*state[4]);
   out_408343791691886305[60] = dt*(-pow(center_to_front, 2)*stiffness_front*state[0] - pow(center_to_rear, 2)*stiffness_rear*state[0])/(rotational_inertia*state[4]) + 1;
   out_408343791691886305[61] = center_to_front*dt*stiffness_front*state[0]/(rotational_inertia*state[1]);
   out_408343791691886305[62] = 0;
   out_408343791691886305[63] = 0;
   out_408343791691886305[64] = 0;
   out_408343791691886305[65] = 0;
   out_408343791691886305[66] = 0;
   out_408343791691886305[67] = 0;
   out_408343791691886305[68] = 0;
   out_408343791691886305[69] = 0;
   out_408343791691886305[70] = 1;
   out_408343791691886305[71] = 0;
   out_408343791691886305[72] = 0;
   out_408343791691886305[73] = 0;
   out_408343791691886305[74] = 0;
   out_408343791691886305[75] = 0;
   out_408343791691886305[76] = 0;
   out_408343791691886305[77] = 0;
   out_408343791691886305[78] = 0;
   out_408343791691886305[79] = 0;
   out_408343791691886305[80] = 1;
}
void h_25(double *state, double *unused, double *out_4032662354692128244) {
   out_4032662354692128244[0] = state[6];
}
void H_25(double *state, double *unused, double *out_7060137937281243065) {
   out_7060137937281243065[0] = 0;
   out_7060137937281243065[1] = 0;
   out_7060137937281243065[2] = 0;
   out_7060137937281243065[3] = 0;
   out_7060137937281243065[4] = 0;
   out_7060137937281243065[5] = 0;
   out_7060137937281243065[6] = 1;
   out_7060137937281243065[7] = 0;
   out_7060137937281243065[8] = 0;
}
void h_24(double *state, double *unused, double *out_3531999184246495067) {
   out_3531999184246495067[0] = state[4];
   out_3531999184246495067[1] = state[5];
}
void H_24(double *state, double *unused, double *out_6640096809461799517) {
   out_6640096809461799517[0] = 0;
   out_6640096809461799517[1] = 0;
   out_6640096809461799517[2] = 0;
   out_6640096809461799517[3] = 0;
   out_6640096809461799517[4] = 1;
   out_6640096809461799517[5] = 0;
   out_6640096809461799517[6] = 0;
   out_6640096809461799517[7] = 0;
   out_6640096809461799517[8] = 0;
   out_6640096809461799517[9] = 0;
   out_6640096809461799517[10] = 0;
   out_6640096809461799517[11] = 0;
   out_6640096809461799517[12] = 0;
   out_6640096809461799517[13] = 0;
   out_6640096809461799517[14] = 1;
   out_6640096809461799517[15] = 0;
   out_6640096809461799517[16] = 0;
   out_6640096809461799517[17] = 0;
}
void h_30(double *state, double *unused, double *out_5774204242298881488) {
   out_5774204242298881488[0] = state[4];
}
void H_30(double *state, double *unused, double *out_143447595789626310) {
   out_143447595789626310[0] = 0;
   out_143447595789626310[1] = 0;
   out_143447595789626310[2] = 0;
   out_143447595789626310[3] = 0;
   out_143447595789626310[4] = 1;
   out_143447595789626310[5] = 0;
   out_143447595789626310[6] = 0;
   out_143447595789626310[7] = 0;
   out_143447595789626310[8] = 0;
}
void h_26(double *state, double *unused, double *out_7897032807670197482) {
   out_7897032807670197482[0] = state[7];
}
void H_26(double *state, double *unused, double *out_7645102817554252327) {
   out_7645102817554252327[0] = 0;
   out_7645102817554252327[1] = 0;
   out_7645102817554252327[2] = 0;
   out_7645102817554252327[3] = 0;
   out_7645102817554252327[4] = 0;
   out_7645102817554252327[5] = 0;
   out_7645102817554252327[6] = 0;
   out_7645102817554252327[7] = 1;
   out_7645102817554252327[8] = 0;
}
void h_27(double *state, double *unused, double *out_969010912968717401) {
   out_969010912968717401[0] = state[3];
}
void H_27(double *state, double *unused, double *out_2318210907590051221) {
   out_2318210907590051221[0] = 0;
   out_2318210907590051221[1] = 0;
   out_2318210907590051221[2] = 0;
   out_2318210907590051221[3] = 1;
   out_2318210907590051221[4] = 0;
   out_2318210907590051221[5] = 0;
   out_2318210907590051221[6] = 0;
   out_2318210907590051221[7] = 0;
   out_2318210907590051221[8] = 0;
}
void h_29(double *state, double *unused, double *out_3916736903324202362) {
   out_3916736903324202362[0] = state[1];
}
void H_29(double *state, double *unused, double *out_4031573634459602254) {
   out_4031573634459602254[0] = 0;
   out_4031573634459602254[1] = 1;
   out_4031573634459602254[2] = 0;
   out_4031573634459602254[3] = 0;
   out_4031573634459602254[4] = 0;
   out_4031573634459602254[5] = 0;
   out_4031573634459602254[6] = 0;
   out_4031573634459602254[7] = 0;
   out_4031573634459602254[8] = 0;
}
void h_28(double *state, double *unused, double *out_1726861058129536211) {
   out_1726861058129536211[0] = state[0];
}
void H_28(double *state, double *unused, double *out_9113972651529132828) {
   out_9113972651529132828[0] = 1;
   out_9113972651529132828[1] = 0;
   out_9113972651529132828[2] = 0;
   out_9113972651529132828[3] = 0;
   out_9113972651529132828[4] = 0;
   out_9113972651529132828[5] = 0;
   out_9113972651529132828[6] = 0;
   out_9113972651529132828[7] = 0;
   out_9113972651529132828[8] = 0;
}
void h_31(double *state, double *unused, double *out_6532809068263374187) {
   out_6532809068263374187[0] = state[8];
}
void H_31(double *state, double *unused, double *out_7029491975404282637) {
   out_7029491975404282637[0] = 0;
   out_7029491975404282637[1] = 0;
   out_7029491975404282637[2] = 0;
   out_7029491975404282637[3] = 0;
   out_7029491975404282637[4] = 0;
   out_7029491975404282637[5] = 0;
   out_7029491975404282637[6] = 0;
   out_7029491975404282637[7] = 0;
   out_7029491975404282637[8] = 1;
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

void car_update_25(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_25, H_25, NULL, in_z, in_R, in_ea, MAHA_THRESH_25);
}
void car_update_24(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<2, 3, 0>(in_x, in_P, h_24, H_24, NULL, in_z, in_R, in_ea, MAHA_THRESH_24);
}
void car_update_30(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_30, H_30, NULL, in_z, in_R, in_ea, MAHA_THRESH_30);
}
void car_update_26(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_26, H_26, NULL, in_z, in_R, in_ea, MAHA_THRESH_26);
}
void car_update_27(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_27, H_27, NULL, in_z, in_R, in_ea, MAHA_THRESH_27);
}
void car_update_29(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_29, H_29, NULL, in_z, in_R, in_ea, MAHA_THRESH_29);
}
void car_update_28(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_28, H_28, NULL, in_z, in_R, in_ea, MAHA_THRESH_28);
}
void car_update_31(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_31, H_31, NULL, in_z, in_R, in_ea, MAHA_THRESH_31);
}
void car_err_fun(double *nom_x, double *delta_x, double *out_7807431280886572175) {
  err_fun(nom_x, delta_x, out_7807431280886572175);
}
void car_inv_err_fun(double *nom_x, double *true_x, double *out_6108977637297046258) {
  inv_err_fun(nom_x, true_x, out_6108977637297046258);
}
void car_H_mod_fun(double *state, double *out_7863625486438816874) {
  H_mod_fun(state, out_7863625486438816874);
}
void car_f_fun(double *state, double dt, double *out_5659262996305498661) {
  f_fun(state,  dt, out_5659262996305498661);
}
void car_F_fun(double *state, double dt, double *out_408343791691886305) {
  F_fun(state,  dt, out_408343791691886305);
}
void car_h_25(double *state, double *unused, double *out_4032662354692128244) {
  h_25(state, unused, out_4032662354692128244);
}
void car_H_25(double *state, double *unused, double *out_7060137937281243065) {
  H_25(state, unused, out_7060137937281243065);
}
void car_h_24(double *state, double *unused, double *out_3531999184246495067) {
  h_24(state, unused, out_3531999184246495067);
}
void car_H_24(double *state, double *unused, double *out_6640096809461799517) {
  H_24(state, unused, out_6640096809461799517);
}
void car_h_30(double *state, double *unused, double *out_5774204242298881488) {
  h_30(state, unused, out_5774204242298881488);
}
void car_H_30(double *state, double *unused, double *out_143447595789626310) {
  H_30(state, unused, out_143447595789626310);
}
void car_h_26(double *state, double *unused, double *out_7897032807670197482) {
  h_26(state, unused, out_7897032807670197482);
}
void car_H_26(double *state, double *unused, double *out_7645102817554252327) {
  H_26(state, unused, out_7645102817554252327);
}
void car_h_27(double *state, double *unused, double *out_969010912968717401) {
  h_27(state, unused, out_969010912968717401);
}
void car_H_27(double *state, double *unused, double *out_2318210907590051221) {
  H_27(state, unused, out_2318210907590051221);
}
void car_h_29(double *state, double *unused, double *out_3916736903324202362) {
  h_29(state, unused, out_3916736903324202362);
}
void car_H_29(double *state, double *unused, double *out_4031573634459602254) {
  H_29(state, unused, out_4031573634459602254);
}
void car_h_28(double *state, double *unused, double *out_1726861058129536211) {
  h_28(state, unused, out_1726861058129536211);
}
void car_H_28(double *state, double *unused, double *out_9113972651529132828) {
  H_28(state, unused, out_9113972651529132828);
}
void car_h_31(double *state, double *unused, double *out_6532809068263374187) {
  h_31(state, unused, out_6532809068263374187);
}
void car_H_31(double *state, double *unused, double *out_7029491975404282637) {
  H_31(state, unused, out_7029491975404282637);
}
void car_predict(double *in_x, double *in_P, double *in_Q, double dt) {
  predict(in_x, in_P, in_Q, dt);
}
void car_set_mass(double x) {
  set_mass(x);
}
void car_set_rotational_inertia(double x) {
  set_rotational_inertia(x);
}
void car_set_center_to_front(double x) {
  set_center_to_front(x);
}
void car_set_center_to_rear(double x) {
  set_center_to_rear(x);
}
void car_set_stiffness_front(double x) {
  set_stiffness_front(x);
}
void car_set_stiffness_rear(double x) {
  set_stiffness_rear(x);
}
}

const EKF car = {
  .name = "car",
  .kinds = { 25, 24, 30, 26, 27, 29, 28, 31 },
  .feature_kinds = {  },
  .f_fun = car_f_fun,
  .F_fun = car_F_fun,
  .err_fun = car_err_fun,
  .inv_err_fun = car_inv_err_fun,
  .H_mod_fun = car_H_mod_fun,
  .predict = car_predict,
  .hs = {
    { 25, car_h_25 },
    { 24, car_h_24 },
    { 30, car_h_30 },
    { 26, car_h_26 },
    { 27, car_h_27 },
    { 29, car_h_29 },
    { 28, car_h_28 },
    { 31, car_h_31 },
  },
  .Hs = {
    { 25, car_H_25 },
    { 24, car_H_24 },
    { 30, car_H_30 },
    { 26, car_H_26 },
    { 27, car_H_27 },
    { 29, car_H_29 },
    { 28, car_H_28 },
    { 31, car_H_31 },
  },
  .updates = {
    { 25, car_update_25 },
    { 24, car_update_24 },
    { 30, car_update_30 },
    { 26, car_update_26 },
    { 27, car_update_27 },
    { 29, car_update_29 },
    { 28, car_update_28 },
    { 31, car_update_31 },
  },
  .Hes = {
  },
  .sets = {
    { "mass", car_set_mass },
    { "rotational_inertia", car_set_rotational_inertia },
    { "center_to_front", car_set_center_to_front },
    { "center_to_rear", car_set_center_to_rear },
    { "stiffness_front", car_set_stiffness_front },
    { "stiffness_rear", car_set_stiffness_rear },
  },
  .extra_routines = {
  },
};

ekf_lib_init(car)
