#pragma once
#include "rednose/helpers/ekf.h"
extern "C" {
void live_update_4(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void live_update_9(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void live_update_10(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void live_update_12(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void live_update_35(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void live_update_32(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void live_update_13(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void live_update_14(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void live_update_33(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void live_H(double *in_vec, double *out_7304326697991488399);
void live_err_fun(double *nom_x, double *delta_x, double *out_4801467506448624538);
void live_inv_err_fun(double *nom_x, double *true_x, double *out_2247108557437656166);
void live_H_mod_fun(double *state, double *out_2465819175073548033);
void live_f_fun(double *state, double dt, double *out_3904334333113200608);
void live_F_fun(double *state, double dt, double *out_3956101082846986216);
void live_h_4(double *state, double *unused, double *out_5547971579996269411);
void live_H_4(double *state, double *unused, double *out_25757183840169366);
void live_h_9(double *state, double *unused, double *out_7038753854287780024);
void live_H_9(double *state, double *unused, double *out_215432462789421279);
void live_h_10(double *state, double *unused, double *out_3133280440032365548);
void live_H_10(double *state, double *unused, double *out_2418505113737090933);
void live_h_12(double *state, double *unused, double *out_7140390772251147643);
void live_H_12(double *state, double *unused, double *out_4993699224191792429);
void live_h_35(double *state, double *unused, double *out_829457081341366400);
void live_H_35(double *state, double *unused, double *out_7739262256516806138);
void live_h_32(double *state, double *unused, double *out_5265072610407020446);
void live_H_32(double *state, double *unused, double *out_4852780833668351642);
void live_h_13(double *state, double *unused, double *out_8810917544790980585);
void live_H_13(double *state, double *unused, double *out_6279064480349314726);
void live_h_14(double *state, double *unused, double *out_7038753854287780024);
void live_H_14(double *state, double *unused, double *out_215432462789421279);
void live_h_33(double *state, double *unused, double *out_1405704258341642512);
void live_H_33(double *state, double *unused, double *out_6491461878171295614);
void live_predict(double *in_x, double *in_P, double *in_Q, double dt);
}