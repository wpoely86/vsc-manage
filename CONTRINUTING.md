We'd love you to contribute back, and here's how you can do it: the branch - hack - pull request cycle.

# License
Contributions can be made under the MIT or
BSD licenses (in the three-clause and two-clause forms, though not the original four-clause form).

Or alteratively the contributor must agree with following contributor agreement:

## Contributor Agreement.
In this case the contributor must agree that Ghent University shall have the irrevocable and perpetual right to make and
distribute copies of any Contribution, as well as to create and distribute collective works and derivative works of
any Contribution, under the Initial License or under any other open source license.
(as defined by The Open Source Initiative (OSI) http://opensource.org/).
Contributor shall identify each Contribution by placing the following notice in its source code adjacent to
Contributor's valid copyright notice: "Licensed to Ghent University under a Contributor Agreement."
The currently acceptable license is GPLv2 or any other GPLv2 compatible license.

Ghent University understands and agrees that Contributor retains copyright in its Contributions.
Nothing in this Contributor Agreement shall be interpreted to prohibit Contributor from licensing its Contributions
under different terms from the Initial License or this Contributor Agreement.


## Preperation

### Fork this repo

First, you'll need to fork this repository on github.

If you do not have a (free) GitHub account yet, you'll need to get one.

You should also register an SSH public key, so you can easily clone, push to and pull from your repository.


### Keep develop up-to-date

The _develop_ branch hosts the latest bleeding-edge version, and is merged into _master_ regularly (after thorough testing).

Make sure you update it every time you create a feature branch (see below):

```bash
git checkout develop
git pull upstream develop
```

## Branch

### Create branch

Create a feature branch for your work, and check it out

```bash
git checkout develop
git branch <BRANCH_NAME>
git checkout <BRANCH_NAME>
```

Make sure to always base your features branches on _develop_, not on _master_!

## Hack

After creating the branch, implement your contributions: new features, new easyblocks for non-supported software, enhancements or updates to existing easyblocks, bug fixes, or rewriting the whole thing in Fortran, whatever you like.

Make sure you commit your work, and try to do it in bite-size chunks, so the commit log remains clear.

For example:

```bash
git add some/new/file.py
git commit -m "support for Linux From Scratch"
```

If you are working on several things at the same time, try and keep things isolated in seperate branches, to keep it manageable (both for you, and for reviewing your contributions, see below).



## Pull request

When you've finished the implementation of a particular contribution, here's how to get it into the main repository (also see https://help.github.com/articles/using-pull-requests/)

### Push your branch

Push your branch to your repository on GitHub:

 ```bash
 git push origin <BRANCH_NAME>
 ```


### Issue a pull request

Issue a pull request for your branch into the main repository, as follows:

 * go to github.com/YOUR\_GITHUB\_LOGIN/<reponame>, and make sure the branch you just pushed is selected (not _master_, but _<BRANCH_NAME>_)

  * issue a pull request (see button at the top of the page) for your branch to the **_develop_** branch of the main repository; **note**: don't issue a pull request to the _master_ branch, as it will be simply closed.

   * make sure to reference the corresponding issue number in the pull request, using the notation # followed by a number, e.g. `#83`

### Review process

A member of our team will then review your pull request, paying attention to what you're contributing, how you implemented it and [code style](Code style).

Most likely, some remarks will be made on your pull request. Note that this is nothing personal, we're just trying to keep the codebase as high quality as possible. Even when an team member makes changes, the same public review process is followed.

Try and act on the remarks made, either by commiting additional changes to your branch, or by replying to the remarks to clarify your work.


### Aftermath

Once your pull request has been reviewed and remarks have been processed, your contribution will be merged into the _develop_ branch of the main repository.

On frequent occasions, the _develop_ branch is merged into the _master_ branch and a new version is tagged, and your contribution truly becomes part of this project.
