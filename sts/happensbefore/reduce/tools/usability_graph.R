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
  out_file <- "../figures/usability.pdf"
}

data <- read.csv(file=csv_file, head=TRUE, sep=",")

# Prepare device
pdf(file=out_file, width=10, height=6)


#colors <- rainbow(2)
colors <- c("black","blue")
linetype <- c(1, 2)
plotchar <- c(3, 4)

yrange <- c(0, 1)
xrange <- c(0, 1)

par(mar = c(5, 6, 1, 1) + 0.3,ps=tsize, cex = 1, cex.main = 1)
plot(xrange, yrange, type="n", xlab="", ylab="", las=1)
mtext("% of violations reduced", side=1, line=4, col=colors[1], las=0, cex=ylab_cex)
mtext("CDF", side=2, line=4, col=colors[1], las=0, cex=ylab_cex)
grid(nx=NULL, ny=NULL, col= "black", lty="dotted", equilogs=FALSE)


# Plot lines

#cdf = ecdf(data$p_final)
lines(ecdf(data$p_iso), lwd=lwidth, lty=linetype[2], col=colors[2], pch=plotchar[1], cex=symb_cex, verticals = TRUE, do.points = TRUE, las=1)
lines(ecdf(data$p_final), lwd=lwidth, lty=linetype[1], col=colors[1], pch=plotchar[2], cex=symb_cex, verticals = TRUE, do.points = TRUE, las=1)

# Title
title("", "")

# Legend
legend("topleft",
        inset=c(0.02, 0.03),
        legend=c("Final clustering","Isomorphic initialization"),
        text.col=colors,
        pch=c(plotchar[2], plotchar[1]),
        cex=1.2,
        pt.cex=symb_cex,
        #lwd=lwidth,
        col=colors,
        y.intersp=2,
        bg="white")

dev.off()

# Output numbers
cat("Isomorphic:\n")
cat(quantile(data$p_iso, c(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)))
cat("\n")
cat("Final:\n")
cat(quantile(data$p_final, c(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)))
cat("\n")
cat("Max:\n")
cat(max(data$p_final))
cat("\n")







