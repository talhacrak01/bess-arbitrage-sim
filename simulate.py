"""
BESS Techno-Economic & Market Arbitrage Simulation
===================================================
Author: Talha Cirak (Energy Systems Engineering)
License: MIT
Case Study: 1 MWh / 500 kW Grid-Scale LFP Storage in Turkish Power Market (EPIAS & TEIAS)
"""

import os
from dataclasses import dataclass
import numpy as np
import matplotlib.pyplot as plt

@dataclass
class BESSConfig:
    nominal_capacity_kwh: float = 1000.0  # 1 MWh
    dod: float = 0.90                     # Depth of Discharge
    pcs_power_kw: float = 500.0           # 0.5C Bi-directional Inverter
    rte: float = 0.865                    # AC-to-AC Round-Trip Efficiency
    capex_usd_per_kwh: float = 145.0      # Turnkey containerized system ($/kWh)
    usd_try_rate: float = 38.0
    annual_opex_rate: float = 0.015       # 1.5% of CAPEX annually
    active_days_per_year: int = 350
    cycle_life: int = 6000                # Cycles to 80% SOH

class BESSModel:
    def __init__(self, config: BESSConfig):
        self.cfg = config
        self.usable_kwh = self.cfg.nominal_capacity_kwh * self.cfg.dod
        self.capex_usd = self.cfg.nominal_capacity_kwh * self.cfg.capex_usd_per_kwh
        self.capex_try = self.capex_usd * self.cfg.usd_try_rate
        self.annual_opex_try = self.capex_try * self.cfg.annual_opex_rate

    def simulate_naive_arbitrage(self, charge_price=1.40, discharge_price=2.85):
        # 1 Cycle per day: Night trough -> Evening peak
        energy_bought = self.usable_kwh / self.cfg.rte
        energy_sold = self.usable_kwh
        daily_cost = energy_bought * charge_price
        daily_rev = energy_sold * discharge_price
        daily_net = daily_rev - daily_cost
        annual_net_try = (daily_net * self.cfg.active_days_per_year) - self.annual_opex_try
        payback = self.capex_try / annual_net_try
        return {
            "daily_net_try": daily_net,
            "annual_net_try": annual_net_try,
            "payback_years": payback,
            "annual_net_usd": annual_net_try / self.cfg.usd_try_rate
        }

    def simulate_advanced_dual_cycle(self):
        # Dual Cycle:
        # Cycle 1: 03:00 Wind trough (1.40) -> 08:30 Morning rush (2.60)
        # Cycle 2: 13:00 Solar trough (1.50) -> 19:30 Evening peak (2.95)
        c1 = (self.usable_kwh * 2.60) - ((self.usable_kwh / self.cfg.rte) * 1.40)
        c2 = (self.usable_kwh * 2.95) - ((self.usable_kwh / self.cfg.rte) * 1.50)
        daily_arb = c1 + c2

        # TEIAS Primary Frequency Regulation (PFC) standby capacity reserve:
        # Inverter capacity 0.5 MW * 18 standby hours * 120 TL/MWh
        daily_ancillary = 0.5 * 18.0 * 120.0
        daily_total = daily_arb + daily_ancillary

        annual_opex_adjusted = self.annual_opex_try * 1.30  # +30% O&M due to 2 cycles
        annual_net_try = (daily_total * self.cfg.active_days_per_year) - annual_opex_adjusted
        payback = self.capex_try / annual_net_try
        return {
            "daily_net_try": daily_total,
            "annual_net_try": annual_net_try,
            "payback_years": payback,
            "annual_net_usd": annual_net_try / self.cfg.usd_try_rate
        }

def generate_plots(output_dir="."):
    # Set dark aesthetic for elite engineering appeal
    plt.style.use('dark_background')
    os.makedirs(output_dir, exist_ok=True)

    hours = np.arange(24)
    # Synthetic realistic EPIAS PTF 24h curve (TL/MWh)
    ptf_tl_mwh = np.array([
        1600, 1480, 1420, 1380, 1400, 1550, 1950, 2450, 2600, 2400,
        2100, 1750, 1520, 1480, 1580, 1850, 2200, 2650, 2980, 2920,
        2700, 2350, 2000, 1750
    ])

    # 1. 24-Hour Dispatch & Market Spread Plot
    fig, ax1 = plt.subplots(figsize=(12, 6), dpi=300)
    fig.patch.set_facecolor('#0d1117')
    ax1.set_facecolor('#161b22')

    line1 = ax1.plot(hours, ptf_tl_mwh, color='#58a6ff', linewidth=3, label='EPİAŞ PTF (TL/MWh)', zorder=3)
    ax1.fill_between(hours, ptf_tl_mwh, color='#58a6ff', alpha=0.15)

    # Highlight Charging Zones (Green)
    ax1.axvspan(2.5, 4.5, color='#2ea043', alpha=0.25, label='Şarj 1 (Gece Rüzgar)')
    ax1.axvspan(12.0, 14.0, color='#2ea043', alpha=0.25, label='Şarj 2 (Öğle Güneş)')

    # Highlight Discharging Zones (Orange)
    ax1.axvspan(7.5, 9.5, color='#f0883e', alpha=0.25, label='Deşarj 1 (Sabah Pik)')
    ax1.axvspan(18.0, 20.0, color='#f0883e', alpha=0.25, label='Deşarj 2 (Akşam Pik)')

    ax1.set_xlabel('Günün Saatleri (24h)', fontsize=12, color='#c9d1d9', fontweight='bold')
    ax1.set_ylabel('Elektrik Fiyatı - PTF (TL/MWh)', fontsize=12, color='#58a6ff', fontweight='bold')
    ax1.set_xticks(hours)
    ax1.grid(color='#30363d', linestyle='--', alpha=0.7)

    plt.title('1 MWh BESS Çift Döngü Arbitraj & Şebeke Fiyat Profili (EPİAŞ GÖP)', fontsize=14, color='#ffffff', pad=15, fontweight='bold')
    ax1.legend(loc='upper left', framealpha=0.8, facecolor='#161b22', edgecolor='#30363d')
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'bess_arbitrage_dispatch.png'), dpi=300)
    plt.close()

    # 2. Cumulative Cash Flow & Payback Comparison Plot
    fig, ax2 = plt.subplots(figsize=(10, 6), dpi=300)
    fig.patch.set_facecolor('#0d1117')
    ax2.set_facecolor('#161b22')

    years = np.arange(0, 16)
    capex = 145000.0 * 38.0 / 1e6  # 5.51 Million TL

    # Net annual incomes in Million TL
    net1 = 0.31
    net2 = 0.96

    cashflow1 = -capex + (years * net1)
    cashflow2 = -capex + (years * net2)

    ax2.axhline(0, color='#8b949e', linestyle='-', linewidth=1.5)
    ax2.plot(years, cashflow1, color='#f85149', linewidth=2.5, marker='o', label='Tek Döngü Yalın Arbitraj (18.0 Yıl - Fizibl Değil)')
    ax2.plot(years, cashflow2, color='#3fb950', linewidth=3.0, marker='s', label='Çift Döngü + TEİAŞ Frekans Kontrolü (5.7 Yıl - Sektör Standardı)')

    ax2.axvline(5.7, color='#3fb950', linestyle='--', alpha=0.7)
    ax2.scatter([5.7], [0], color='#2ea043', s=120, zorder=5)
    ax2.annotate('Başabaş: ~5.7 Yıl', xy=(5.7, 0), xytext=(6.5, -1.5),
                 color='#3fb950', fontweight='bold', fontsize=11,
                 arrowprops=dict(facecolor='#3fb950', shrink=0.08, width=1.5, headwidth=8))

    ax2.set_xlabel('Yatırım Yılı', fontsize=12, color='#c9d1d9', fontweight='bold')
    ax2.set_ylabel('Kümülatif Nakit Akışı (Milyon TL)', fontsize=12, color='#c9d1d9', fontweight='bold')
    ax2.set_xticks(years)
    ax2.grid(color='#30363d', linestyle='--', alpha=0.7)

    plt.title('1 MWh BESS Kümülatif Amortisman Karşılaştırması', fontsize=14, color='#ffffff', pad=15, fontweight='bold')
    ax2.legend(loc='lower right', framealpha=0.8, facecolor='#161b22', edgecolor='#30363d')
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'bess_payback_comparison.png'), dpi=300)
    plt.close()
    print("Grafikler basariyla uretildi.")

if __name__ == "__main__":
    cfg = BESSConfig()
    model = BESSModel(cfg)
    res1 = model.simulate_naive_arbitrage()
    res2 = model.simulate_advanced_dual_cycle()

    print("\n--- SIMULASYON SONUCLARI ---")
    print(f"Tek Dongu Payback  : {res1['payback_years']:.1f} Yil")
    print(f"Gelisimis Payback  : {res2['payback_years']:.1f} Yil")
    generate_plots("bess-arbitrage-sim")
