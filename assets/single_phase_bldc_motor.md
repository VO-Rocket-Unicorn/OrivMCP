# Single-Phase BLDC Motor Simulation README

## Purpose

This document explains the mathematical model, equations, parameters, and simulation structure required to simulate a single-phase Brushless DC (BLDC) motor.

The goal is to correctly implement:

* Electrical dynamics
* Mechanical dynamics
* Electromagnetic torque generation
* Back-EMF generation
* Rotor motion
* PWM voltage excitation
* Commutation logic
* Numerical integration

This document focuses on physics-based time-domain simulation.

---

# 1. Overview of a Single-Phase BLDC Motor

A single-phase BLDC motor contains:

* One stator winding (or one electrical phase)
* A permanent magnet rotor
* Electronic commutation
* Position-dependent back-EMF
* Electromagnetic torque generation

Unlike a brushed DC motor:

* There are no brushes
* Commutation is electronic
* Back-EMF depends on rotor angle
* Torque depends on current and rotor position

The simulation must therefore model:

1. Electrical current dynamics
2. Rotor mechanical dynamics
3. Electromagnetic coupling
4. Rotor-angle-dependent waveforms

---

# 2. Core State Variables

The simulation typically uses the following state variables.

## Electrical State

### Phase Current

[
i(t)
]

Units:

* Amperes (A)

---

## Mechanical States

### Rotor Angular Velocity

[
\omega(t)
]

Units:

* radians/second (rad/s)

---

### Rotor Mechanical Angle

[
\theta(t)
]

Units:

* radians (rad)

---

# 3. Fundamental Electrical Equation

The electrical behavior of the phase winding is governed by Kirchhoff’s Voltage Law (KVL).

## Single-Phase Voltage Equation

[
V(t) = Ri(t) + L\frac{di(t)}{dt} + e(\theta, \omega)
]

Where:

* (V(t)) = applied phase voltage
* (R) = phase resistance
* (L) = phase inductance
* (i(t)) = phase current
* (e(\theta, \omega)) = back electromotive force (back-EMF)

Rearranged:

[
\frac{di}{dt} = \frac{V - Ri - e}{L}
]

This is the primary electrical differential equation.

---

# 4. Back-EMF Equation

Back-EMF is generated due to rotor motion.

## General Back-EMF Equation

[
e(\theta, \omega) = K_e \cdot f(\theta) \cdot \omega
]

Where:

* (K_e) = back-EMF constant
* (f(\theta)) = normalized back-EMF waveform
* (\omega) = rotor speed

---

# 5. Back-EMF Waveform

The waveform depends on motor construction.

Common models:

* Trapezoidal
* Sinusoidal
* Measured lookup table

---

## 5.1 Sinusoidal Back-EMF

[
f(\theta) = \sin(p\theta)
]

Thus:

[
e = K_e \sin(p\theta) \omega
]

Where:

* (p) = pole pair count

---

## 5.2 Trapezoidal Back-EMF

A piecewise trapezoidal function is often used.

Example normalized waveform:

[
f(\theta) \in [-1, 1]
]

The exact implementation may use:

* Piecewise equations
* Lookup tables
* Interpolation

---

# 6. Electromagnetic Torque Equation

The generated torque depends on current and rotor position.

## General Torque Equation

[
T_e = K_t \cdot f(\theta) \cdot i
]

Where:

* (T_e) = electromagnetic torque
* (K_t) = torque constant
* (f(\theta)) = same waveform used for back-EMF
* (i) = phase current

---

## Sinusoidal Torque Example

[
T_e = K_t \sin(p\theta) i
]

---

# 7. Mechanical Dynamics Equation

Rotor dynamics follow Newton’s rotational law.

## Rotor Motion Equation

[
J\frac{d\omega}{dt} = T_e - T_L - B\omega
]

Rearranged:

[
\frac{d\omega}{dt} = \frac{T_e - T_L - B\omega}{J}
]

Where:

* (J) = rotor inertia
* (T_L) = load torque
* (B) = viscous damping coefficient
* (\omega) = angular velocity

---

# 8. Rotor Angle Equation

Rotor angle evolves from angular velocity.

[
\frac{d\theta}{dt} = \omega
]

This equation updates rotor position.

---

# 9. Complete State-Space Model

The complete state vector:

[
\mathbf{x} =
\begin{bmatrix}
i \
\omega \
\theta
\end{bmatrix}
]

---

## Differential Equations

### Current Dynamics

[
\frac{di}{dt} = \frac{V - Ri - e(\theta,\omega)}{L}
]

---

### Speed Dynamics

[
\frac{d\omega}{dt} = \frac{T_e - T_L - B\omega}{J}
]

---

### Rotor Angle Dynamics

[
\frac{d\theta}{dt} = \omega
]

---

# 10. Relationship Between Torque Constant and Back-EMF Constant

In SI units:

[
K_t = K_e
]

Provided:

* (K_t) is in Nm/A
* (K_e) is in V/(rad/s)

This equivalence is commonly assumed.

---

# 11. Electrical Angle vs Mechanical Angle

Electrical angle:

[
\theta_e = p\theta_m
]

Where:

* (\theta_e) = electrical angle
* (\theta_m) = mechanical angle
* (p) = pole pairs

Back-EMF and torque equations often use electrical angle.

---

# 12. PWM Voltage Modeling

The applied voltage is usually generated using PWM.

## Average Voltage Approximation

[
V = D \cdot V_{dc}
]

Where:

* (D) = duty cycle
* (V_{dc}) = DC bus voltage

---

## Bipolar Excitation

Some single-phase BLDC systems apply:

[
V = \pm D V_{dc}
]

depending on commutation state.

---

# 13. Commutation Logic

Single-phase BLDC motors require electronic commutation.

Commutation determines:

* Current direction
* Applied voltage polarity
* Torque direction

Commutation is usually based on:

* Rotor angle
* Hall sensor state
* Back-EMF zero crossing

---

## Example Commutation Rule

If:

[
\sin(p\theta) > 0
]

Apply:

[
V = +DV_{dc}
]

Else:

[
V = -DV_{dc}
]

---

# 14. Hall Sensor Modeling

Optional but often useful.

Hall sensors provide rotor position information.

A simple Hall signal:

[
H(\theta) =
\begin{cases}
1 & \sin(p\theta) \ge 0 \
0 & \sin(p\theta) < 0
\end{cases}
]

This can drive commutation logic.

---

# 15. Friction Models

## 15.1 Viscous Friction

[
T_f = B\omega
]

---

## 15.2 Coulomb Friction

Optional:

[
T_f = T_c \cdot sign(\omega)
]

Where:

* (T_c) = Coulomb friction torque

---

# 16. Extended Mechanical Equation

Including Coulomb friction:

[
J\frac{d\omega}{dt} = T_e - T_L - B\omega - T_c sign(\omega)
]

---

# 17. Thermal Modeling (Optional)

Resistance may vary with temperature.

## Temperature-Dependent Resistance

[
R(T) = R_0[1 + \alpha(T - T_0)]
]

Where:

* (R_0) = reference resistance
* (\alpha) = temperature coefficient
* (T) = temperature

---

# 18. Power Equations

## Electrical Input Power

[
P_{in} = Vi
]

---

## Mechanical Output Power

[
P_{mech} = T_e\omega
]

---

## Copper Loss

[
P_{cu} = i^2R
]

---

# 19. Efficiency Equation

[
\eta = \frac{P_{mech}}{P_{in}}
]

---

# 20. Numerical Simulation

The system is simulated by integrating differential equations over time.

Common numerical methods:

* Euler Method
* RK2
* RK4
* Adaptive ODE Solvers

---

# 21. RK4 Integration Structure

For a generic state equation:

[
\frac{dx}{dt} = f(x,t)
]

RK4 computes:

[
k_1 = f(x_n,t_n)
]

[
k_2 = f(x_n + \frac{h}{2}k_1,t_n+\frac{h}{2})
]

[
k_3 = f(x_n + \frac{h}{2}k_2,t_n+\frac{h}{2})
]

[
k_4 = f(x_n + hk_3,t_n+h)
]

Update:

[
x_{n+1}=x_n+\frac{h}{6}(k_1+2k_2+2k_3+k_4)
]

---

# 22. Required Simulation Parameters

This section lists all parameters commonly required.

---

# 22.1 Electrical Parameters

| Parameter         | Symbol | Units     | Description                 |
| ----------------- | ------ | --------- | --------------------------- |
| Phase Resistance  | R      | Ohms      | Stator winding resistance   |
| Phase Inductance  | L      | Henry     | Stator winding inductance   |
| Back-EMF Constant | Ke     | V/(rad/s) | Voltage generated per speed |
| Torque Constant   | Kt     | Nm/A      | Torque per ampere           |
| DC Bus Voltage    | Vdc    | Volts     | Supply voltage              |

---

# 22.2 Mechanical Parameters

| Parameter        | Symbol | Units   | Description              |
| ---------------- | ------ | ------- | ------------------------ |
| Rotor Inertia    | J      | kg·m²   | Mechanical inertia       |
| Viscous Friction | B      | Nms/rad | Damping coefficient      |
| Coulomb Friction | Tc     | Nm      | Static friction torque   |
| Load Torque      | TL     | Nm      | External mechanical load |

---

# 22.3 Geometric Parameters

| Parameter  | Symbol | Units   | Description          |
| ---------- | ------ | ------- | -------------------- |
| Pole Pairs | p      | Integer | Number of pole pairs |

---

# 22.4 Control Parameters

| Parameter         | Symbol | Units | Description                 |
| ----------------- | ------ | ----- | --------------------------- |
| PWM Duty Cycle    | D      | 0–1   | PWM modulation ratio        |
| PWM Frequency     | fpwm   | Hz    | PWM switching frequency     |
| Control Frequency | fc     | Hz    | Controller update frequency |

---

# 22.5 Initial Conditions

| Variable            | Symbol |
| ------------------- | ------ |
| Initial Current     | i0     |
| Initial Speed       | ω0     |
| Initial Rotor Angle | θ0     |

---

# 23. Typical Simulation Inputs

The simulator usually accepts:

* Supply voltage
* PWM duty cycle
* Load torque
* Initial speed
* Initial angle
* Simulation time
* Time step

---

# 24. Typical Simulation Outputs

The simulator usually produces:

* Phase current
* Rotor speed
* Rotor angle
* Electromagnetic torque
* Back-EMF
* Input power
* Efficiency
* PWM waveforms

---

# 25. Minimal Simulation Algorithm

## Step 1

Initialize:

* current
* speed
* angle

---

## Step 2

Compute electrical angle:

[
\theta_e = p\theta
]

---

## Step 3

Compute back-EMF waveform:

[
f(\theta)
]

---

## Step 4

Compute back-EMF:

[
e = K_e f(\theta)\omega
]

---

## Step 5

Compute electromagnetic torque:

[
T_e = K_t f(\theta)i
]

---

## Step 6

Compute derivatives:

[
\frac{di}{dt}
]

[
\frac{d\omega}{dt}
]

[
\frac{d\theta}{dt}
]

---

## Step 7

Integrate states using RK4 or another solver.

---

## Step 8

Advance time and repeat.

---

# 26. Recommended State-Space Function Structure

A simulator implementation usually defines:

```python
state = [i, omega, theta]
```

The derivative function returns:

```python
dstate_dt = [
    di_dt,
    domega_dt,
    dtheta_dt
]
```

---

# 27. Example Continuous-Time Model

## Electrical Equation

[
\frac{di}{dt} = \frac{V - Ri - K_e f(\theta)\omega}{L}
]

---

## Torque Equation

[
T_e = K_t f(\theta)i
]

---

## Mechanical Equation

[
\frac{d\omega}{dt} = \frac{K_t f(\theta)i - T_L - B\omega}{J}
]

---

## Rotor Position Equation

[
\frac{d\theta}{dt} = \omega
]

---

# 28. Common Simplifications

Many simulators simplify the system by:

* Ignoring saturation
* Ignoring temperature effects
* Using sinusoidal back-EMF
* Assuming constant parameters
* Ignoring switching ripple
* Using averaged PWM voltage

These are acceptable for many control and system-level simulations.

---

# 29. Advanced Modeling Extensions

More advanced simulations may include:

* Magnetic saturation
* Iron losses
* Eddy current losses
* Thermal dynamics
* Sensor noise
* Dead-time effects
* Switching device losses
* Nonlinear inductance
* Lookup-table back-EMF
* FEA-derived torque maps

---

# 30. Minimum Parameters Needed for a Basic Working Simulation

The absolute minimum parameters are:

```text
R      Phase resistance
L      Phase inductance
Ke     Back-EMF constant
Kt     Torque constant
J      Rotor inertia
B      Viscous friction
p      Pole pairs
Vdc    Supply voltage
TL     Load torque
```

Initial conditions:

```text
i0
omega0
theta0
```

---

# 31. Recommended Units

Always use SI units.

| Quantity   | SI Unit |
| ---------- | ------- |
| Voltage    | V       |
| Current    | A       |
| Resistance | Ohm     |
| Inductance | H       |
| Torque     | Nm      |
| Speed      | rad/s   |
| Angle      | rad     |
| Inertia    | kg·m²   |

---

# 32. Important Notes

## Angle Wrapping

Rotor angle should usually be wrapped:

[
\theta = \theta \bmod 2\pi
]

---

## Stability

Very large time steps can destabilize simulation.

Typical simulation time steps:

* 1e-6 to 1e-4 seconds

depending on switching frequency and stiffness.

---

## Numerical Issues

High PWM frequency and low inductance can create stiff dynamics.

Adaptive solvers may help.

---

# 33. Summary of Core Equations

## Electrical Dynamics

[
\frac{di}{dt} = \frac{V - Ri - e}{L}
]

---

## Back-EMF

[
e = K_e f(\theta)\omega
]

---

## Electromagnetic Torque

[
T_e = K_t f(\theta)i
]

---

## Mechanical Dynamics

[
\frac{d\omega}{dt} = \frac{T_e - T_L - B\omega}{J}
]

---

## Rotor Position

[
\frac{d\theta}{dt} = \omega
]

---

# 34. Final Notes for AI Systems

A correct single-phase BLDC simulation requires:

1. Coupled electrical and mechanical differential equations
2. Rotor-position-dependent back-EMF
3. Rotor-position-dependent torque production
4. Numerical integration over time
5. Proper unit consistency
6. Proper commutation logic

The most important dependency chain is:

```text
Rotor Angle
    ↓
Back-EMF Waveform
    ↓
Back-EMF Voltage
    ↓
Current Dynamics
    ↓
Electromagnetic Torque
    ↓
Mechanical Acceleration
    ↓
Rotor Speed
    ↓
Rotor Angle
```

This feedback loop is the core of BLDC motor simulation.
