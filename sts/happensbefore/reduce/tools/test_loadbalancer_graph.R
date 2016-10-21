#!/bin/Rscript

# Test Script to create a graph out of a csv
args <- commandArgs(TRUE)

if (length(args)!=1) {
  stop("Exactly one parameter needed (path to csv).n", call.=FALSE)
} else {
  csv_file <- args[1]
  eval_dir <- dirname(csv_file)
  out_file <- paste(eval_dir,"/loadbalancer.pdf",sep="")
}

data <- read.csv(file=csv_file, head=TRUE, sep=",")

d <- split(data, data$steps)


# Prepare Data
# prepare lines
s <- numeric(0)
race <- list(c(),c(),c())
clus <- list(c(),c(),c())


for (dat in d){
    s <- c(s, dat$steps[1])
    race[[1]] <- c(race[[1]], quantile(dat$races, c(0.05)))
    race[[2]] <- c(race[[2]], quantile(dat$races, c(0.50)))
    race[[3]] <- c(race[[3]], quantile(dat$races, c(0.95)))
    clus[[1]] <- c(clus[[1]], quantile(dat$clusters, c(0.05)))
    clus[[2]] <- c(clus[[2]], quantile(dat$clusters, c(0.50)))
    clus[[3]] <- c(clus[[3]], quantile(dat$clusters, c(0.95)))
}

# Prepare device
pdf(file=out_file)

# Prepare Plot
xrange <- range(data$steps)
yrange1 <- c(0, max(data$races))
yrange2 <- c(0, 10)

#colors <- rainbow(2)
colors <- c("black", "red")
linetype <- c(1:length(race))
plotchar <- seq(15, 15+length(race), 1)

# OLD
# plot(xrange, yrange1, type="n", xlab="Steps", ylab="Races")

# New
par(mar = c(5, 4, 4, 4) + 0.3)
plot(xrange, yrange1, type="n", xlab="Steps", ylab="")
axis(side=2, at = pretty(yrange1), col=colors[1], col.axis=colors[1])
mtext("Number of Races", side=2, line=3, col=colors[1])
# End New

# Plot lines
for (i in 1:length(race)){
    lines(s, race[[i]], type="b", lwd="1.5", lty=linetype[i], col=colors[1], pch=plotchar[i])
}

par(new = TRUE)
plot(xrange, yrange2, type = "n", axes = FALSE, bty = "n", xlab = "", ylab = "")
axis(side=4, at = pretty(yrange2), col=colors[2], col.axis=colors[2])
mtext("Final number of Clusters", side=4, line=3, col=colors[2])

for (i in 1:length(clus)){
    lines(s, clus[[i]], type="b", lwd="1.5", lty=linetype[i], col=colors[2], pch=plotchar[i])
}

# Title
title("Races vs. Clusters", "Floodlight Loadbalancer StarTopology4")

# Legend
legend("topleft",
        legend=c("5th percentile", "median", "95th percentile", "5th percentile", "median", "95th percentile"),
        text.col=c(colors[1], colors[1], colors[1], colors[2], colors[2], colors[2]),
        pch=c(plotchar, plotchar),
        col=c(colors[1], colors[1], colors[1], colors[2], colors[2], colors[2]))

#legend(xrange[1], yrange1[2], c("5th percentile", "median", "95th percentile", "5th percentile", "median", "95th percentile"), cex=0.8, col=colors, pch=plotchar, lty=linetype, title="Legend")

dev.off()
