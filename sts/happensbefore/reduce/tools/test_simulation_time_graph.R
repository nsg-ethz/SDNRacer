#!/bin/Rscript

# Test Script to create a graph out of a csv
args <- commandArgs(TRUE)

if (length(args)!=1) {
  stop("Exactly one parameter needed (path to csv).n", call.=FALSE)
} else {
  csv_file <- args[1]
  eval_dir <- dirname(csv_file)
  out_file <- paste(eval_dir,"/sim_time.png",sep="")
}

data <- read.csv(file=csv_file, head=TRUE, sep=",")

step_data <- split(data, data$steps)

# Prepare Data
s <- unique(data$steps)

# Prepare device
png(file=out_file)


#colors <- rainbow(2)
colors <- rainbow(length(step_data))
linetype <- c(1:length(step_data))
plotchar <- seq(15, 15+length(step_data), 1)

yrange <- c(0, 1)
xrange <- c(0, max(data$sim_time))

plot(xrange, yrange, type="n", xlab="Simulation time in seconds", ylab="CDF")


# Plot lines
for (i in 1:length(step_data)){
    cdf = ecdf(step_data[[i]]$sim_time)
    lines(cdf, type="b", lwd="1.5", lty=linetype[i], col=colors[i], pch=plotchar[i])
}

# Title
title("Simulation Time", "")

# Legend
legend("topleft",
        title="Steps",
        legend=s,
        text.col=colors,
        pch=c(plotchar, plotchar),
        col=colors)

dev.off()
