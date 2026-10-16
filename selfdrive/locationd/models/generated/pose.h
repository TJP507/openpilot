#pragma once
#include "rednose/helpers/ekf.h"
extern "C" {
void pose_update_4(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void pose_update_10(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void pose_update_13(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void pose_update_14(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void pose_err_fun(double *nom_x, double *delta_x, double *out_1302557212303107234);
void pose_inv_err_fun(double *nom_x, double *true_x, double *out_645935160919976454);
void pose_H_mod_fun(double *state, double *out_3435950681424489829);
void pose_f_fun(double *state, double dt, double *out_5840201724917908869);
void pose_F_fun(double *state, double dt, double *out_2069028585121272448);
void pose_h_4(double *state, double *unused, double *out_8602233424768964049);
void pose_H_4(double *state, double *unused, double *out_4633898163307387933);
void pose_h_10(double *state, double *unused, double *out_4500317655482818027);
void pose_H_10(double *state, double *unused, double *out_2288732070358272906);
void pose_h_13(double *state, double *unused, double *out_6663006413571036728);
void pose_H_13(double *state, double *unused, double *out_7846171988639720734);
void pose_h_14(double *state, double *unused, double *out_8667838621540344432);
void pose_H_14(double *state, double *unused, double *out_1551109731012015637);
void pose_predict(double *in_x, double *in_P, double *in_Q, double dt);
}