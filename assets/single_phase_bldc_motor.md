# Single-Phase BLDC Motor Simulation Requirements

## Complete Differential Equation Set

### 1. Current Dynamics

\[
\frac{di}{dt} =
\frac{
V - Ri - K_e f(\theta_e)\omega
}{L}
\]

Where:

- \(i\) = phase current
- \(V\) = applied voltage
- \(R\) = phase resistance
- \(L\) = phase inductance
- \(K_e\) = back-EMF constant
- \(f(\theta_e)\) = normalized back-EMF waveform
- \(\omega\) = rotor angular velocity

---

### 2. Speed Dynamics

\[
\frac{d\omega}{dt} =
\frac{
K_t f(\theta_e)i - T_L - B\omega
}{J}
\]

Where:

- \(\omega\) = rotor angular velocity
- \(K_t\) = torque constant
- \(T_L\) = load torque
- \(B\) = viscous friction coefficient
- \(J\) = rotor inertia

---

### 3. Rotor Angle Dynamics

\[
\frac{d\theta}{dt} = \omega
\]

Where:

- \(\theta\) = rotor mechanical angle
- \(\omega\) = rotor angular velocity

---

# Electrical Angle

\[
\theta_e = p\theta
\]

Where:

- \(p\) = number of pole pairs
- \(\theta\) = mechanical rotor angle

---

# Back-EMF Waveform

Example sinusoidal waveform:

\[
f(\theta_e) = \sin(\theta_e)
\]

---

# Required Parameters

## Electrical Parameters

| Parameter | Symbol | Units |
|---|---|---|
| Phase resistance | \(R\) | Ohm |
| Phase inductance | \(L\) | Henry (H) |
| Back-EMF constant | \(K_e\) | V/(rad/s) |
| Torque constant | \(K_t\) | Nm/A |
| DC supply voltage | \(V_{dc}\) | Volts |

---

## Mechanical Parameters

| Parameter | Symbol | Units |
|---|---|---|
| Rotor inertia | \(J\) | kg·m² |
| Viscous friction | \(B\) | Nms/rad |
| Load torque | \(T_L\) | Nm |

---

## Geometric Parameters

| Parameter | Symbol |
|---|---|
| Pole pairs | \(p\) |

---

## Control Parameters

| Parameter | Symbol |
|---|---|
| PWM duty cycle | \(D\) |
| PWM frequency | \(f_{pwm}\) |

---

## Initial Conditions

| Variable | Description |
|---|---|
| \(i_0\) | Initial phase current |
| \(\omega_0\) | Initial rotor speed |
| \(\theta_0\) | Initial rotor angle |
