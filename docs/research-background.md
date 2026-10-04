# Research Background

[Back to the project introduction](../README.md)

IndoEuroPop began with a question: could epidemic mortality, alongside migration
and other demographic processes, help explain changes in steppe-related
ancestry during the Late Neolithic and Early Bronze Age in western Eurasia?
The project turns that motivation into explicit, replaceable model assumptions
that can be compared with curated ancient-DNA ancestry estimates.

## The motivating hypothesis

The author's particular interest is the possible role of *Yersinia pestis* in
population changes associated with the expansion of Yamnaya-related steppe
pastoralists. One hypothesis to investigate is that differences in prior
exposure, susceptibility, or survival could have affected the relative sizes
of incoming and resident populations. A reduction in one population before or
during migration could change later ancestry proportions even without assuming
that every encounter involved violent displacement.

That hypothesis raises several distinct questions:

- Could epidemic mortality change ancestry trajectories enough to distinguish
  it from migration alone?
- Would differences in susceptibility or survival be necessary, and what
  independent evidence could constrain them?
- Could animal contact, mobility, or exchange networks help explain exposure
  patterns, and what evidence would distinguish those pathways?
- Would the same mechanism work across regions and time periods, or would it
  require different assumptions for each comparison?

These are research questions. The package does not establish steppe-derived
immunity, the origin or transmission route of a pathogen, or a plague-driven
explanation for ancestry change. Its configurable epidemic-risk differences
are assumptions to vary, not estimates of ancient immune adaptation.

## Why compare several mechanisms?

The original motivation also drew on comparisons with later epidemic and
migration episodes, including the medieval Black Death and European contact
with the Americas. Those comparisons help formulate questions about mortality,
mobility, and social disruption; they do not establish the same causal sequence
for prehistoric Eurasia. This project does not use those analogies as parameter
estimates or evidence that an ancient population had a particular immunity.

Migration, fertility and reproductive differences, climate stress, violence,
and subsistence changes are alternative or interacting explanations to
consider. Some have explicit parameters in the current simulator; others
remain research directions. Comparing them requires stating their assumptions
and checking whether different mechanisms produce similar ancestry curves.
A better fit alone cannot establish which historical mechanism occurred.

The broader interest includes populations often described in terms of
steppe-related, western hunter-gatherer, and Anatolian farmer ancestry. The
current core simulator uses the simplified source labels `local` and `steppe`;
it does not independently resolve all of those ancestry components. Nor does
it directly model the spread of Indo-European languages. Genetic ancestry,
archaeological culture, and language affiliation must remain separate concepts.

## From motivation to a testable comparison

The working approach is to start with transparent population-count models,
prepare documented ancestry targets, and inspect fit and held-out behavior.
Before changing a model to explain a residual, review the target's samples,
chronology, uncertainty, publication metadata, and ancestry-estimation method.
Then compare alternative assumptions using reproducible inputs and explicit
validation splits.

The implemented calibration workflows support exploratory comparisons, not
established historical causal conclusions. Modern ancestry distributions are
part of the broader motivation, but the documented real-data workflow currently
centers on curated ancient-DNA targets.

Continue with [architecture and current scope](architecture.md) for the model's
engineering decisions and limitations, [target curation](target-curation.md)
for the evidence requirements, or the [project plan](project-plan.md) for the
longer research roadmap.
