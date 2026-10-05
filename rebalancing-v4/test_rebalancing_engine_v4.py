import json
import math
import unittest
import numpy as np
import pandas as pd
import importlib.util
from pathlib import Path

APP_PATH = Path(__file__).with_name('rebalancing_app_v4_complete.py')
spec = importlib.util.spec_from_file_location('rebv4', APP_PATH)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class TestEngine(unittest.TestCase):
    def setUp(self):
        self.df = m.validate_portfolio(pd.DataFrame(m.DEFAULT_PORTFOLIO), ntsg_is_plug=True)

    def test_default_valid(self):
        self.assertEqual(len(self.df), 10)
        self.assertEqual(int((self.df.role == 'efficient_core').sum()), 1)

    def test_8_8_allocation_nav_closes(self):
        p = m.apply_role_target(self.df, 'gold', 8.0)
        p = m.apply_role_target(p, 'trend', 8.0)
        orders, post, cash, nav, d = m.allocate_cash(p, 200000.0, 'NAV Totale', True)
        pre = float((p.shares * p.price).sum())
        self.assertAlmostEqual(nav, pre + 200000.0, places=6)
        self.assertGreaterEqual(cash, 0)
        self.assertTrue((post.shares_delta >= 0).all())
        self.assertTrue(np.allclose(post.shares_delta, np.floor(post.shares_delta)))
        self.assertGreater(float(post.loc[post.role=='efficient_core','post_value'].sum()), 0)

    def test_plug_target_conflict(self):
        p = self.df.copy()
        p.loc[p.role=='efficient_core','target'] = 5
        with self.assertRaises(ValueError):
            m.validate_portfolio(p, ntsg_is_plug=True)
        m.validate_portfolio(p, ntsg_is_plug=False)

    def test_legacy_target_rejected(self):
        p = self.df.copy(); p.loc[p.sleeve=='Legacy Core','target'] = 1
        with self.assertRaises(ValueError): m.validate_portfolio(p, ntsg_is_plug=True)

    def test_exposure_model_uses_declared_proxies(self):
        p = m.apply_role_target(self.df, 'gold', 8.0); p = m.apply_role_target(p, 'trend', 8.0)
        _, post, _, nav, _ = m.allocate_cash(p, 200000.0, 'NAV Totale', True)
        proxy_exp, macro, detail = m.build_exposure_model(post, nav)
        for proxy in ['VT','AVUV','SCZ','MTUM','BND','GLD','DBMF']:
            self.assertIn(proxy, proxy_exp.index)
        self.assertGreater(macro['bond'], 0)
        self.assertGreater(sum(macro.values())/nav, 1.0)

    def test_euler_random_psd_closure(self):
        rng=np.random.default_rng(7)
        for _ in range(250):
            n=7; A=rng.normal(size=(n,n)); cov=A@A.T/10000
            e=np.abs(rng.normal(size=n))*100000; nav=500000
            sigma,gross,mcr,rc,pct=m.euler_risk_from_nav(e,nav,cov)
            self.assertTrue(np.isfinite(sigma)); self.assertAlmostEqual(float(rc.sum()), sigma, places=9)

    def test_config_roundtrip(self):
        settings=m._deepcopy_settings(); txt=m.export_config(self.df,settings)
        p,s,notes=m.parse_config_bytes(txt.encode())
        self.assertEqual(len(p),len(self.df)); self.assertEqual(s['risk_years'],5)

    def test_legacy_config_migration(self):
        old=self.df.copy()
        old['proxy']='VT'
        old.loc[old.role=='gold','proxy']='GLD'; old.loc[old.role=='trend','proxy']='DBMF'; old.loc[old.role=='efficient_core','proxy']='NTSX'
        old=old.drop(columns=['role','price_asof','price_source','equity_proxy','bond_proxy','gold_proxy','trend_proxy'])
        raw=json.dumps(old.to_dict(orient='records')).encode()
        p,s,notes=m.parse_config_bytes(raw)
        ec=p.loc[p.role=='efficient_core'].iloc[0]
        self.assertEqual(ec.equity_proxy,'VT'); self.assertEqual(ec.bond_proxy,'BND')
        self.assertTrue(notes)

    def test_historical_tail_metrics(self):
        rng=np.random.default_rng(1); s=pd.Series(rng.normal(0.0002,0.01,1500))
        var,es=m.historical_tail_metrics(s)
        self.assertTrue(np.isfinite(var)); self.assertTrue(np.isfinite(es)); self.assertGreaterEqual(es,var)

    def test_simulation(self):
        p=m.apply_role_target(self.df,'gold',8); p=m.apply_role_target(p,'trend',8)
        _,post,cash,nav,_=m.allocate_cash(p,200000,'NAV Totale',True)
        sim=m.annual_simulation(post,cash,50000,15,'NAV Totale',True,m.DEFAULT_SETTINGS['expected_returns_pct'])
        self.assertEqual(len(sim),16); self.assertTrue((sim.NAV>0).all()); self.assertTrue((sim['Leva Lorda']>0).all())

    def test_quote_freshness(self):
        import datetime as dt
        self.assertTrue(m.quote_is_fresh('2026-10-02','Yahoo',today=dt.date(2026,10,5)))
        self.assertFalse(m.quote_is_fresh('2026-09-28','Yahoo',today=dt.date(2026,10,5)))
        self.assertFalse(m.quote_is_fresh('2026-10-05','Manuale',today=dt.date(2026,10,5)))

if __name__=='__main__': unittest.main(verbosity=2)