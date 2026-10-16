#pragma once
#include "rednose/helpers/ekf.h"
extern "C" {
void car_update_25(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_24(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_30(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_26(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_27(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_29(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_28(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_31(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_err_fun(double *nom_x, double *delta_x, double *out_7807431280886572175);
void car_inv_err_fun(double *nom_x, double *true_x, double *out_6108977637297046258);
void car_H_mod_fun(double *state, double *out_7863625486438816874);
void car_f_fun(double *state, double dt, double *out_5659262996305498661);
void car_F_fun(double *state, double dt, double *out_408343791691886305);
void car_h_25(double *state, double *unused, double *out_4032662354692128244);
void car_H_25(double *state, double *unused, double *out_7060137937281243065);
void car_h_24(double *state, double *unused, double *out_3531999184246495067);
void car_H_24(double *state, double *unused, double *out_6640096809461799517);
void car_h_30(double *state, double *unused, double *out_5774204242298881488);
void car_H_30(double *state, double *unused, double *out_143447595789626310);
void car_h_26(double *state, double *unused, double *out_7897032807670197482);
void car_H_26(double *state, double *unused, double *out_7645102817554252327);
void car_h_27(double *state, double *unused, double *out_969010912968717401);
void car_H_27(double *state, double *unused, double *out_2318210907590051221);
void car_h_29(double *state, double *unused, double *out_3916736903324202362);
void car_H_29(double *state, double *unused, double *out_4031573634459602254);
void car_h_28(double *state, double *unused, double *out_1726861058129536211);
void car_H_28(double *state, double *unused, double *out_9113972651529132828);
void car_h_31(double *state, double *unused, double *out_6532809068263374187);
void car_H_31(double *state, double *unused, double *out_7029491975404282637);
void car_predict(double *in_x, double *in_P, double *in_Q, double dt);
void car_set_mass(double x);
void car_set_rotational_inertia(double x);
void car_set_center_to_front(double x);
void car_set_center_to_rear(double x);
void car_set_stiffness_front(double x);
void car_set_stiffness_rear(double x);
}