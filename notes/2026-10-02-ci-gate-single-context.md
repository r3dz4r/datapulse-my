# CI gate uses one required check context

The required `deterministic-safety-net` context must have exactly one producer
for a given head SHA. A push-event run and a pull-request run can otherwise
publish the same required context for that SHA. When a branch ruleset requires
the context, both matching runs must conclude successfully, so a hung duplicate
can hold the merge even after its twin has passed.

On 2026-10-01T15:57Z through 2026-10-02T21:55Z, the push-event run hung in
`Install Pandoc` at 16:00:52Z and remained in progress for 5h40m. Its pull
request twin passed in 11m23s on the same SHA, while the health-automation merge
PR remained blocked because the duplicate was pending. The blocked merge stopped
public health publication; the publish transaction correctly refused to publish
onto a base that did not contain `origin/main`. Twelve push-event runs of this
workflow were created in the preceding day, roughly one every five to ten
minutes.

The deterministic safety net now runs only for pull requests and explicit
workflow dispatches. Every job also has a finite job timeout. A timeout bounds a
hang by converting indefinite pending into a definite failure; it does not by
itself restore a blocked merge. The failed required check still needs to be
resolved before the merge can proceed.
