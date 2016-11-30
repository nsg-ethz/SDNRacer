#!/bin/Rscript

# Test Script to create a graph out of a csv
args <- commandArgs(TRUE)

options(scipen=999)
tsize <- 24         # Textsize
ylab_cex <- 1       # Scaling of y axis lables
lwidth <- 1            # Linewidth
symb_cex <- 2       # Scaling of symbol size
llen <- 5           # Line length in legend

if (length(args)!=1) {
  stop("Exactly one parameter needed (path to csv).n", call.=FALSE)
} else {
  csv_file <- args[1]
  eval_dir <- dirname(csv_file)
  out_file <- "../figures/timing.pdf"
}

data <- read.csv(file=csv_file, head=TRUE, sep=",")
data <- subset(data, steps==200)

# Prepare device
pdf(file=out_file, width=10, height=6)


#colors <- rainbow(2)
colors <- c('black')
linetype <- c(1)
plotchar <- c(3)

yrange <- c(0, 1)
xrange <- c(0.01, 1000)

par(mar = c(5, 6, 1, 1) + 0.3,ps=tsize, cex = 1, cex.main = 1)
plot(xrange, yrange, type="n",log="x", xlab="", ylab="", las=1)
mtext("Time in seconds", side=1, line=4, col=colors[1], las=0, cex=ylab_cex)
mtext("CDF", side=2, line=4, col=colors[1], las=0, cex=ylab_cex)
grid(nx=NULL, ny=NULL, col= "blue", lty="dotted", equilogs=FALSE)

# Plot lines
cdf = ecdf(data$bigbug)
lines(cdf, lwd=lwidth, lty=linetype[1], col=colors[1], pch=plotchar[1], cex=symb_cex, verticals = TRUE, do.points = TRUE, las=1)


# Title
title("", "")

# Legend
#legend("topleft",
#        title="Steps",
#        legend=s,
#        text.col=colors,
#        pch=c(plotchar, plotchar),
#        pt.cex=symb_cex,
#        #lwd=lwidth,
#        col=colors,
#        y.intersp=1.5,
#        bg="white")

dev.off()

cat("Quantile: \n")
cat(quantile(data$bigbug, c(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95)))
cat("\n")
cat("Max: ")
cat(max(data$bigbug))
cat("\n")




