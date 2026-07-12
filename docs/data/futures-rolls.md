# Futures Rolls

Roll policy is part of the dataset contract, not a display preference. The active reference-data home is `data/reference/<symbol>/roll_calendars/`.

Record:

- contract symbols and roll timestamps
- timezone and session used to determine volume
- whether prices are adjusted
- treatment of duplicate or overlapping bars
- source and version of explicit calendars

Do not assume parity with charting-platform continuous symbols. Verify the same contract selection and adjustment rules independently.
