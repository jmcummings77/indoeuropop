#!/usr/bin/env Rscript
#
# Headless qpAdm runner for the IndoEuroPop target-data workflow.
#
# It precomputes f2 statistics with ADMIXTOOLS 2, runs one qpAdm model per AADR
# target group, then writes a per-individual CSV accepted by:
#
#   uv run indoeuropop load-qpadm-estimates \
#     --qpadm-estimates data/qpadm/steppe-estimates.csv \
#     --ancestry-estimates-out results/sample-ancestry-estimates.csv
#
# This script intentionally lives outside the Python package and test coverage:
# it requires system R, a compiler-built ADMIXTOOLS 2 installation, and local
# AADR genotype files.

args <- commandArgs(trailingOnly = TRUE)
if ("--help" %in% args || "-h" %in% args) {
  cat("Usage: Rscript scripts/run_qpadm.R --prefix PREFIX --targets TSV --out CSV --f2dir DIR\n")
  quit(status = 0)
}

suppressMessages({
  library(admixtools)
  library(data.table)
})

STEPPE_OVERRIDE <- ""
FARMER_OVERRIDE <- ""
WHG_OVERRIDE <- ""

STEPPE_PATTERN <- "Yamnaya"
FARMER_PATTERN <- "Barcin|Anatolia_N|T.rkiye_N|Turkey_N|Boncuklu|Anatolia_Barcin"
WHG_PATTERN <- "Villabruna|Loschbour|IronGates|Iron_Gates|Koros_HG|_WHG$|WHG$"

RIGHT_OVERRIDE <- character(0)
RIGHT_CANDIDATES <- c(
  "Mbuti.DG", "Han.DG", "Onge.DG", "Papuan.DG", "Karitiana.DG", "Ust_Ishim.DG",
  "Russia_Ust_Ishim", "Russia_Kostenki14", "Russia_MA1_HG", "China_Tianyuan",
  "Ethiopia_4500BP", "Israel_Natufian", "Iran_GanjDareh_N",
  "Morocco_Iberomaurusian", "Jordan_PPNB", "Russia_AfontovaGora3"
)

parse_args <- function(values) {
  parsed <- list(
    prefix = "data/aadr",
    targets = "curation/aadr-v66-western-europe-qpadm-targets.tsv",
    out = "data/qpadm/steppe-estimates.csv",
    f2dir = "data/qpadm/f2"
  )
  i <- 1
  while (i <= length(values)) {
    key <- sub("^--", "", values[[i]])
    if (!is.null(parsed[[key]])) {
      parsed[[key]] <- values[[i + 1]]
      i <- i + 2
    } else {
      stop(sprintf("unknown argument: %s", values[[i]]))
    }
  }
  parsed
}

resolve_prefix <- function(prefix) {
  exts <- c(".geno", ".snp", ".ind")
  if (all(file.exists(paste0(prefix, exts)))) return(prefix)
  search_dir <- if (dir.exists(prefix)) prefix else dirname(prefix)
  geno <- list.files(search_dir, pattern = "\\.geno$", full.names = TRUE)
  if (length(geno) == 0) {
    stop(sprintf("no genotype files near '%s'", prefix))
  }
  pick <- geno[grepl("1240", geno, ignore.case = TRUE)]
  if (length(pick) == 0) pick <- geno
  candidate <- sub("\\.geno$", "", pick[[1]])
  if (!all(file.exists(paste0(candidate, exts)))) {
    stop(sprintf("incomplete genotype set for '%s'", candidate))
  }
  message(sprintf("Using genotype prefix: %s", candidate))
  candidate
}

pick_largest <- function(pop_counts, pattern) {
  cand <- pop_counts[grepl(pattern, group, ignore.case = TRUE) & !grepl("-o", group)]
  if (nrow(cand) == 0) return(NA_character_)
  cand[order(-N)][1]$group
}

resolve_source <- function(pop_counts, override, pattern, role) {
  label <- if (nzchar(override)) override else pick_largest(pop_counts, pattern)
  if (is.na(label)) {
    stop(sprintf("could not auto-pick a %s source with pattern /%s/", role, pattern))
  }
  label
}

read_targets <- function(path, present) {
  raw <- fread(path, header = FALSE, sep = "\t", blank.lines.skip = TRUE)
  if (ncol(raw) < 2) stop("target file needs region and group columns")
  setnames(raw, names(raw)[1:2], c("region", "group"))
  raw <- raw[!grepl("^\\s*#", region)]
  raw <- raw[!(tolower(region) == "region" & tolower(group) %in% c("group_id", "aadr_group_id"))]
  target_groups <- unique(raw$group)
  missing_targets <- setdiff(target_groups, present)
  if (length(missing_targets) > 0) {
    message(sprintf(
      "Dropping %d target group(s) absent from .ind: %s",
      length(missing_targets), paste(missing_targets, collapse = ", ")
    ))
  }
  intersect(target_groups, present)
}

opts <- parse_args(args)
opts$prefix <- resolve_prefix(opts$prefix)

ind <- as.data.table(read.table(
  paste0(opts$prefix, ".ind"),
  header = FALSE,
  stringsAsFactors = FALSE,
  col.names = c("genetic_id", "sex", "group")
))
pop_counts <- ind[, .N, by = group]
present <- pop_counts$group

STEPPE_SOURCE <- resolve_source(pop_counts, STEPPE_OVERRIDE, STEPPE_PATTERN, "steppe")
FARMER_SOURCE <- resolve_source(pop_counts, FARMER_OVERRIDE, FARMER_PATTERN, "farmer/EEF")
WHG_SOURCE <- resolve_source(pop_counts, WHG_OVERRIDE, WHG_PATTERN, "WHG")
LEFT <- c(STEPPE_SOURCE, FARMER_SOURCE, WHG_SOURCE)

RIGHT <- if (length(RIGHT_OVERRIDE) > 0) RIGHT_OVERRIDE else intersect(RIGHT_CANDIDATES, present)
if (length(RIGHT) < 4) {
  stop("too few outgroups present; edit RIGHT_CANDIDATES or RIGHT_OVERRIDE")
}

target_groups <- read_targets(opts$targets, present)
if (length(target_groups) == 0) stop("no target groups are present in the .ind file")

missing <- setdiff(c(LEFT, RIGHT), present)
if (length(missing) > 0) {
  stop(sprintf("populations missing in .ind: %s", paste(missing, collapse = ", ")))
}

cat("Resolved qpAdm model:\n")
cat(sprintf("  LEFT  (sources):   %s\n", paste(LEFT, collapse = ", ")))
cat(sprintf("  RIGHT (outgroups): %s\n", paste(RIGHT, collapse = ", ")))

all_pops <- unique(c(LEFT, RIGHT, target_groups))
cat(sprintf("Extracting f2 for %d populations into %s ...\n", length(all_pops), opts$f2dir))
dir.create(opts$f2dir, recursive = TRUE, showWarnings = FALSE)
extract_f2(opts$prefix, opts$f2dir, pops = all_pops, overwrite = TRUE)

estimate_group <- function(group) {
  res <- tryCatch(
    qpadm(opts$f2dir, left = LEFT, right = RIGHT, target = group),
    error = function(error) {
      message(sprintf("  qpAdm failed for %s: %s", group, conditionMessage(error)))
      NULL
    }
  )
  if (is.null(res)) return(NULL)
  weights <- as.data.table(res$weights)
  steppe <- weights[left == STEPPE_SOURCE]
  p_value <- as.data.table(res$rankdrop)[1L]$p
  data.table(
    group = group,
    steppe_fraction = steppe$weight,
    stderr = steppe$se,
    qpadm_pvalue = p_value
  )
}

group_estimates <- rbindlist(lapply(target_groups, estimate_group), fill = TRUE)
if (nrow(group_estimates) == 0) {
  stop("no qpAdm models succeeded; check population labels and outgroups")
}

per_individual <- merge(
  ind[, .(genetic_id, group)],
  group_estimates,
  by = "group"
)[, .(`Genetic ID` = genetic_id, steppe_fraction, stderr, qpadm_pvalue)]

dir.create(dirname(opts$out), recursive = TRUE, showWarnings = FALSE)
fwrite(per_individual, opts$out)
cat(sprintf(
  "Wrote %d individual estimates across %d groups to %s\n",
  nrow(per_individual), nrow(group_estimates), opts$out
))
