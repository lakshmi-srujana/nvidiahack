# Local demo

Start both services using [README.md](README.md). No API key is needed for the
offline scenario flow.

1. Select **Flash flood · nominal**, then **Verify plan**. Confirm the result
   passes and a certificate digest appears.
2. Click **Launch simulation**. Observe the simulated location and clock.
3. Select **Wind spike** and click **Inject event**. The status becomes
   intervention required, the certificate disappears, and the simulation
   pauses. Select **Replan & verify** to see the wind violation and blocked
   launch. A survivor event demonstrates a passing remaining-route replan.
4. Select **Dam breach** and verify. The restricted-zone violation prevents a
   certificate. Repeat with **Low battery**.
5. Expand **Create a survey area**, enter a survey instruction and a small
   rectangle, then create, verify, and launch it.

The scenario parameters and safety limits are demo assumptions. An AI proposal
is optional and incurs Nebius usage when selected. The UI does not currently
claim automatic coverage planning, autonomous replanning, or real flight.
